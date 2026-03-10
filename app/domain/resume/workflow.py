import asyncio
from typing import Literal

import httpx
from langgraph.cache.memory import InMemoryCache
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import CachePolicy

from app.core.exceptions import ErrorCode, PositionMismatchError
from app.core.logging import get_logger
from app.domain.resume.error_handler import (
    create_error_state,
    handle_connection_error,
    handle_data_error,
    handle_http_error,
)
from app.domain.resume.schemas import (
    ProjectInfoDict,
    ResumeState,
)
from app.domain.resume.schemas.plan import BulletPlan, ProjectPlan
from app.domain.resume.service import (
    collect_project_info,
    collect_repo_contexts,
    collect_user_stats,
    filter_tech_stack_by_position,
    validate_position_match,
)
from app.domain.resume.workflow_utils import evaluate_with_fallback, has_error, make_should_retry
from app.infra.github.client import parse_repo_url
from app.infra.llm.client import evaluate_resume, generate_resume, plan_resume

logger = get_logger(__name__)


async def collect_data_node(state: ResumeState) -> ResumeState:
    """데이터 수집 노드: 프로젝트 정보, 레포 컨텍스트, 사용자 통계 수집"""
    request = state["request"]
    logger.info("collect_data_node 시작", repos=len(request.repo_urls), position=request.position)

    try:
        project_info, repo_contexts = await asyncio.gather(
            collect_project_info(request),
            collect_repo_contexts(request),
        )

        if not project_info:
            return create_error_state(
                state,
                ErrorCode.COLLECT_DATA_FAILED,
                "프로젝트 정보 수집 실패",
            )

        username, _ = parse_repo_url(request.repo_urls[0])
        user_stats = await collect_user_stats(username, request.github_token)

        logger.info(
            "collect_data_node 완료", projects=len(project_info), contexts=len(repo_contexts)
        )

        matched_projects = []
        for project in project_info:
            is_valid, error_msg = validate_position_match(
                request.position,
                project.get("dependencies", []),
            )
            if not is_valid:
                logger.warning(
                    "포지션 불일치 스킵",
                    repo=project.get("repo_name"),
                    position=request.position,
                    error=error_msg,
                )
                continue
            matched_projects.append(project)

        if not matched_projects:
            return create_error_state(
                state,
                ErrorCode.POSITION_MISMATCH,
                "모든 프로젝트에서 포지션에 맞는 기술 스택을 찾지 못했습니다",
            )

        return {
            **state,
            "project_info": matched_projects,
            "repo_contexts": repo_contexts,
            "user_stats": user_stats,
        }

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e, state, "collect_data_node", ErrorCode.GITHUB_API_ERROR, "GitHub API 오류"
        )

    except ValueError as e:
        logger.error("collect_data_node 값 오류", error=str(e), exc_info=True)
        return create_error_state(
            state,
            ErrorCode.INVALID_INPUT,
            f"잘못된 입력값: {e}",
        )

    except (KeyError, TypeError) as e:
        return handle_data_error(
            e, state, "collect_data_node", ErrorCode.DATA_PARSE_ERROR, "데이터 파싱 오류"
        )


async def plan_node(state: ResumeState) -> ResumeState:
    """Plan 노드: Gemini가 프로젝트별로 병렬 분석하여 불릿 작성 계획 생성"""
    project_info = state.get("project_info", [])
    repo_contexts = state.get("repo_contexts", {})
    request = state["request"]
    session_id = state.get("session_id")

    logger.info("plan_node 시작", projects=len(project_info))

    async def _plan_single_project(project: ProjectInfoDict) -> ProjectPlan:
        repo_name = project.get("repo_name", "")
        repo_context = repo_contexts.get(repo_name)
        context_dict = None
        if repo_context:
            context_dict = {
                "languages": repo_context.languages,
                "description": repo_context.description,
                "readme_summary": repo_context.readme_summary,
            }

        return await plan_resume(
            project_info=project,
            position=request.position,
            repo_context=context_dict,
            session_id=session_id,
        )

    tasks = [_plan_single_project(p) for p in project_info]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    plans = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            repo_name = project_info[i].get("repo_name", "unknown")
            logger.warning("plan 실패, 폴백 생성", repo=repo_name, error=str(result))
            fallback = _create_fallback_plan(project_info[i])
            plans.append(fallback)
        else:
            plans.append(result)

    logger.info("plan_node 완료", plans=len(plans))

    return {
        **state,
        "project_plans": plans,
    }


def _create_fallback_plan(project: ProjectInfoDict) -> ProjectPlan:
    """Plan 실패 시 커밋 메시지를 그대로 사용하는 폴백 plan 생성"""
    messages = project.get("messages", [])
    feature_messages = [m for m in messages if "feat" in m.lower() or "PR #" in m]
    if not feature_messages:
        feature_messages = messages[:8]

    bullet_plans = []
    for msg in feature_messages[:8]:
        clean_msg = msg.replace("commit: ", "").split(" | ")[0]
        bullet_plans.append(
            BulletPlan(
                source_commits=[msg],
                suggested_content=clean_msg,
                technical_detail="폴백 - 원본 커밋 메시지 사용",
            )
        )

    if len(bullet_plans) < 5:
        for msg in messages:
            if msg not in feature_messages:
                clean_msg = msg.replace("commit: ", "").split(" | ")[0]
                bullet_plans.append(
                    BulletPlan(
                        source_commits=[msg],
                        suggested_content=clean_msg,
                        technical_detail="폴백 - 원본 커밋 메시지 사용",
                    )
                )
            if len(bullet_plans) >= 5:
                break

    return ProjectPlan(
        project_name=project.get("repo_name", ""),
        repo_url=project.get("repo_url", ""),
        recommended_tech_stack=project.get("dependencies", [])[:8],
        bullet_plans=bullet_plans,
        skipped_commits=[],
    )


def _format_plans_for_generator(plans: list[ProjectPlan]) -> str:
    """ProjectPlan 리스트를 vLLM 프롬프트용 텍스트로 변환"""
    total = len(plans)
    sections = []
    for i, plan in enumerate(plans, 1):
        lines = [
            f"=== 프로젝트 {i}/{total}: {plan.project_name} ===",
            f"URL: {plan.repo_url}",
            f"tech_stack: {', '.join(plan.recommended_tech_stack)}",
            "",
        ]
        for j, bp in enumerate(plan.bullet_plans, 1):
            lines.append(f"불릿 {j}: {bp.suggested_content}")
            lines.append(f"  근거: {', '.join(bp.source_commits[:3])}")
            if bp.technical_detail and bp.technical_detail != "폴백 - 원본 커밋 메시지 사용":
                lines.append(f"  기술: {bp.technical_detail}")
        lines.append(f"=== 프로젝트 {i}/{total} 끝 ===")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


async def generate_node(state: ResumeState) -> ResumeState:
    """이력서 생성 노드: Plan 기반으로 이력서 JSON 생성"""
    logger.info("generate_node 시작")

    project_info = state.get("project_info")
    if not project_info:
        logger.error("generate_node: project_info 없음, 데이터 수집 실패")
        return create_error_state(
            state,
            ErrorCode.GENERATE_ERROR,
            "프로젝트 정보가 없습니다",
        )

    request = state["request"]
    session_id = state.get("session_id")
    project_plans = state.get("project_plans", [])
    retry_count = state.get("retry_count", 0)

    generation_plans = _format_plans_for_generator(project_plans) if project_plans else ""

    evaluation_feedback = state.get("evaluation_feedback", "")
    previous_resume = state.get("resume_data")
    is_retry = bool(evaluation_feedback and previous_resume)

    feedback = evaluation_feedback if is_retry else ""
    previous_resume_json = previous_resume.model_dump_json(indent=2) if is_retry else ""

    if is_retry:
        logger.info("generate_node 재시도", retry_count=retry_count)

    try:
        resume_data = await generate_resume(
            project_info=project_info,
            position=request.position,
            session_id=session_id,
            generation_plans=generation_plans,
            feedback=feedback,
            previous_resume_json=previous_resume_json,
        )

        for project in resume_data.projects:
            project.tech_stack = filter_tech_stack_by_position(
                project.tech_stack,
                request.position,
            )

        logger.info("generate_node 완료", projects=len(resume_data.projects))

        return {
            **state,
            "resume_data": resume_data,
            "retry_count": retry_count + 1 if is_retry else retry_count,
        }

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(
            e,
            state,
            "generate_node",
            ErrorCode.LLM_API_ERROR,
        )

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e,
            state,
            "generate_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
        )

    except PositionMismatchError as e:
        logger.warning("generate_node 포지션 불일치", error=str(e))
        return create_error_state(
            state,
            ErrorCode.POSITION_MISMATCH,
            e.detail or e.message,
        )

    except ValueError as e:
        logger.error("generate_node 생성 오류", error=str(e))
        return create_error_state(
            state,
            ErrorCode.GENERATE_VALIDATION_ERROR,
            f"이력서 생성 검증 오류: {e}",
        )

    except (KeyError, TypeError) as e:
        return handle_data_error(
            e,
            state,
            "generate_node",
            ErrorCode.GENERATE_PARSE_ERROR,
            "이력서 생성 중 데이터 오류",
        )


async def evaluate_node(state: ResumeState) -> ResumeState:
    """이력서 평가 노드: Gemini가 커밋 근거 검증, 실패 시 피드백 저장"""
    resume_data = state.get("resume_data")
    if not resume_data:
        logger.error("evaluate_node: resume_data 없음")
        return {**state, "evaluation": "pass", "evaluation_feedback": ""}

    request = state["request"]
    session_id = state.get("session_id")
    project_info = state.get("project_info", [])

    repo_contexts = state.get("repo_contexts", {})

    return await evaluate_with_fallback(
        state,
        lambda: evaluate_resume(
            resume_data=resume_data,
            position=request.position,
            project_info=project_info,
            repo_contexts=repo_contexts,
            session_id=session_id,
        ),
        node_name="evaluate_node",
    )


def should_continue(state: ResumeState) -> Literal["plan", "end"]:
    """에러 상태 확인: 에러 있으면 종료, 없으면 plan 노드로"""
    return "end" if has_error(state, "should_continue") else "plan"


def _should_continue_after_plan(state: ResumeState) -> Literal["generate", "end"]:
    """plan 후 에러 확인"""
    return "end" if has_error(state, "_should_continue_after_plan") else "generate"


_node_cache = InMemoryCache()


def _should_continue_after_generate(state: ResumeState) -> Literal["evaluate", "end"]:
    """generate 후 에러 확인: 에러 있으면 종료, 없으면 evaluate로"""
    return "end" if has_error(state, "_should_continue_after_generate") else "evaluate"


def create_resume_workflow() -> CompiledStateGraph:
    """이력서 생성 워크플로우 생성 - Plan-Generate-Evaluate Reflection 패턴"""
    workflow = StateGraph(ResumeState)

    collect_data_cache_policy = CachePolicy(ttl=3600)
    workflow.add_node("collect_data", collect_data_node, cache_policy=collect_data_cache_policy)
    workflow.add_node("plan", plan_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("evaluate", evaluate_node)

    workflow.set_entry_point("collect_data")

    workflow.add_conditional_edges(
        "collect_data",
        should_continue,
        {
            "plan": "plan",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "plan",
        _should_continue_after_plan,
        {
            "generate": "generate",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "generate",
        _should_continue_after_generate,
        {
            "evaluate": "evaluate",
            "end": END,
        },
    )

    _should_retry_generate = make_should_retry(max_retries=2, retry_node="generate")
    workflow.add_conditional_edges(
        "evaluate",
        _should_retry_generate,
        {
            "generate": "generate",
            "end": END,
        },
    )

    return workflow.compile(cache=_node_cache)
