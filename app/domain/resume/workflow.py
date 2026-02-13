import asyncio
from typing import Literal

import httpx
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import settings
from app.core.exceptions import ErrorCode, PositionMismatchError
from app.core.logging import get_logger
from app.domain.resume.error_handler import (
    create_error_state,
    handle_data_error,
    handle_http_error,
)
from app.domain.resume.schemas import (
    ProjectInfoDict,
    RepoContext,
    ResumeData,
    ResumeRequest,
    ResumeState,
)
from app.domain.resume.service import (
    collect_project_info,
    collect_repo_contexts,
    collect_user_stats,
    filter_tech_stack_by_position,
    validate_position_match,
)
from app.domain.resume.workflow_utils import (
    evaluate_with_fallback,
    has_error,
    make_should_retry,
    should_evaluate,
)
from app.infra.github.client import parse_repo_url
from app.infra.llm.client import evaluate_resume, generate_resume

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

        for project in project_info:
            is_valid, error_msg = validate_position_match(
                request.position,
                project.get("dependencies", []),
            )
            if not is_valid:
                logger.warning(
                    "포지션 불일치",
                    repo=project.get("repo_name"),
                    position=request.position,
                    error=error_msg,
                )
                return create_error_state(
                    state,
                    ErrorCode.POSITION_MISMATCH,
                    f"{project.get('repo_name')}: {error_msg}",
                )

        return {
            **state,
            "project_info": project_info,
            "repo_contexts": repo_contexts,
            "user_stats": user_stats,
            "retry_count": 0,
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


async def generate_node(state: ResumeState) -> ResumeState:
    """이력서 생성 노드: 배치 처리로 이력서 생성"""
    retry_count = state.get("retry_count", 0)
    evaluation = state.get("evaluation")

    if evaluation == "fail":
        retry_count += 1
        logger.info("generate_node 재시도", retry_count=retry_count)
    else:
        logger.info("generate_node 시작", retry_count=retry_count)

    project_info = state.get("project_info")
    if not project_info:
        logger.error("generate_node: project_info 없음, 데이터 수집 실패")
        return create_error_state(
            state,
            ErrorCode.GENERATE_ERROR,
            "프로젝트 정보가 없습니다",
            retry_count=retry_count,
        )

    request = state["request"]
    repo_contexts = state.get("repo_contexts", {})
    user_stats = state.get("user_stats")
    session_id = state.get("session_id")
    feedback = state.get("evaluation_feedback")

    try:
        resume_data = await _generate_in_batches(
            project_info=project_info,
            request=request,
            repo_contexts=repo_contexts,
            user_stats=user_stats,
            feedback=feedback,
            session_id=session_id,
        )

        for project in resume_data.projects:
            project.tech_stack = filter_tech_stack_by_position(
                project.tech_stack,
                request.position,
            )

        logger.info("generate_node 완료", projects=len(resume_data.projects))

        return {
            **state,
            "retry_count": retry_count,
            "resume_data": resume_data,
        }

    except httpx.ConnectError as e:
        logger.error("generate_node LLM 서버 연결 실패", error=str(e))
        return create_error_state(
            state,
            ErrorCode.LLM_API_ERROR,
            "LLM 서버 연결 실패",
            retry_count=retry_count,
        )

    except httpx.TimeoutException as e:
        logger.error("generate_node LLM 요청 타임아웃", error=str(e))
        return create_error_state(
            state,
            ErrorCode.LLM_API_ERROR,
            "LLM 요청 타임아웃",
            retry_count=retry_count,
        )

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e,
            state,
            "generate_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
            retry_count=retry_count,
        )

    except PositionMismatchError as e:
        logger.warning("generate_node 포지션 불일치", error=str(e))
        return create_error_state(
            state,
            ErrorCode.POSITION_MISMATCH,
            e.detail or e.message,
            retry_count=retry_count,
        )

    except ValueError as e:
        logger.error("generate_node 생성 오류", error=str(e))
        return create_error_state(
            state,
            ErrorCode.GENERATE_VALIDATION_ERROR,
            f"이력서 생성 검증 오류: {e}",
            retry_count=retry_count,
        )

    except (KeyError, TypeError) as e:
        return handle_data_error(
            e,
            state,
            "generate_node",
            ErrorCode.GENERATE_PARSE_ERROR,
            "이력서 생성 중 데이터 오류",
            retry_count=retry_count,
        )


async def evaluate_node(state: ResumeState) -> ResumeState:
    """이력서 평가 노드: 품질 평가 수행"""
    resume_data = state["resume_data"]
    request = state["request"]
    session_id = state.get("session_id")

    async def _evaluate():
        return await evaluate_resume(
            resume_data=resume_data,
            position=request.position,
            session_id=session_id,
        )

    return await evaluate_with_fallback(state, _evaluate)


def should_continue(state: ResumeState) -> Literal["generate", "end"]:
    """에러 상태 확인: 에러 있으면 종료, 없으면 다음 노드로"""
    return "end" if has_error(state, "should_continue") else "generate"


def create_resume_workflow() -> CompiledStateGraph:
    """이력서 생성 워크플로우 생성"""
    workflow = StateGraph(ResumeState)

    workflow.add_node("collect_data", collect_data_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("evaluate", evaluate_node)

    workflow.set_entry_point("collect_data")

    workflow.add_conditional_edges(
        "collect_data",
        should_continue,
        {
            "generate": "generate",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "generate",
        should_evaluate,
        {
            "evaluate": "evaluate",
            "end": END,
        },
    )

    should_retry = make_should_retry(settings.workflow_max_retries, "generate")
    workflow.add_conditional_edges(
        "evaluate",
        should_retry,
        {
            "generate": "generate",
            "end": END,
        },
    )

    return workflow.compile()


async def _generate_in_batches(
    project_info: list[ProjectInfoDict],
    request: ResumeRequest,
    repo_contexts: dict[str, RepoContext],
    user_stats: dict | None = None,
    feedback: str | None = None,
    session_id: str | None = None,
) -> ResumeData:
    """프로젝트를 배치로 나누어 이력서 생성 후 병합"""
    if len(project_info) <= settings.workflow_batch_size:
        return await generate_resume(
            project_info=project_info,
            position=request.position,
            repo_urls=request.repo_urls,
            repo_contexts=repo_contexts,
            user_stats=user_stats,
            feedback=feedback,
            session_id=session_id,
        )

    batches = [
        project_info[i : i + settings.workflow_batch_size]
        for i in range(0, len(project_info), settings.workflow_batch_size)
    ]
    logger.info("배치 처리 시작", total=len(project_info), batches=len(batches))

    tasks = []
    for batch_idx, batch in enumerate(batches):
        batch_repo_urls = [p["repo_url"] for p in batch]
        batch_repo_names = [p["repo_name"] for p in batch]
        batch_contexts = {
            name: ctx for name, ctx in repo_contexts.items() if name in batch_repo_names
        }

        task = generate_resume(
            project_info=batch,
            position=request.position,
            repo_urls=batch_repo_urls,
            repo_contexts=batch_contexts,
            user_stats=user_stats if batch_idx == 0 else None,
            feedback=feedback,
            session_id=session_id,
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    return _merge_resume_results(results)


def _merge_resume_results(results: list[ResumeData]) -> ResumeData:
    """여러 ResumeData를 하나로 병합"""
    all_projects = []

    for result in results:
        all_projects.extend(result.projects)

    return ResumeData(projects=all_projects)
