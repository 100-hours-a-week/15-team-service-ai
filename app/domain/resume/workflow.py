import asyncio
from typing import Literal

import httpx
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import settings
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.resume.schemas import RepoContext, ResumeData, ResumeRequest, ResumeState
from app.domain.resume.service import (
    collect_project_info,
    collect_repo_contexts,
    collect_user_stats,
)
from app.infra.github.client import parse_repo_url
from app.infra.llm.client import evaluate_resume, generate_resume

logger = get_logger(__name__)


async def collect_data_node(state: ResumeState) -> ResumeState:
    """데이터 수집 노드: 프로젝트 정보, 레포 컨텍스트, 사용자 통계 수집"""
    request = state["request"]
    logger.info(
        "collect_data_node 시작 repos=%d position=%s",
        len(request.repo_urls),
        request.position,
    )

    try:
        project_info, repo_contexts = await asyncio.gather(
            collect_project_info(request),
            collect_repo_contexts(request),
        )

        if not project_info:
            return {
                **state,
                "error_code": ErrorCode.COLLECT_DATA_FAILED,
                "error_message": "프로젝트 정보 수집 실패",
            }

        username, _ = parse_repo_url(request.repo_urls[0])
        user_stats = await collect_user_stats(username, request.github_token)

        logger.info(
            "collect_data_node 완료 projects=%d contexts=%d",
            len(project_info),
            len(repo_contexts),
        )

        return {
            **state,
            "project_info": project_info,
            "repo_contexts": repo_contexts,
            "user_stats": user_stats,
            "retry_count": 0,
        }

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        logger.error("collect_data_node HTTP 오류 status=%d", status_code)
        return {
            **state,
            "error_code": ErrorCode.GITHUB_API_ERROR,
            "error_message": f"GitHub API 오류: HTTP {status_code}",
        }

    except ValueError as e:
        logger.error("collect_data_node 값 오류 error=%s", e)
        return {
            **state,
            "error_code": ErrorCode.INVALID_INPUT,
            "error_message": f"잘못된 입력값: {e}",
        }

    except (KeyError, TypeError) as e:
        logger.error("collect_data_node 데이터 오류 error=%s", e, exc_info=True)
        return {
            **state,
            "error_code": ErrorCode.DATA_PARSE_ERROR,
            "error_message": f"데이터 파싱 오류: {e}",
        }


async def generate_node(state: ResumeState) -> ResumeState:
    """이력서 생성 노드: 배치 처리로 이력서 생성"""
    retry_count = state.get("retry_count", 0)
    evaluation = state.get("evaluation")

    if evaluation == "fail":
        retry_count += 1
        logger.info("generate_node 재시도 retry_count=%d", retry_count)
    else:
        logger.info("generate_node 시작 retry_count=%d", retry_count)

    project_info = state.get("project_info")
    if not project_info:
        logger.error("generate_node: project_info 없음, 데이터 수집 실패")
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.GENERATE_ERROR,
            "error_message": "프로젝트 정보가 없습니다",
        }

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

        logger.info("generate_node 완료 projects=%d", len(resume_data.projects))

        return {
            **state,
            "retry_count": retry_count,
            "resume_data": resume_data,
        }

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        logger.error("generate_node LLM API 오류 status=%d", status_code)
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.LLM_API_ERROR,
            "error_message": f"LLM API 오류: HTTP {status_code}",
        }

    except ValueError as e:
        logger.error("generate_node 생성 오류 error=%s", e)
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.GENERATE_VALIDATION_ERROR,
            "error_message": f"이력서 생성 검증 오류: {e}",
        }

    except (KeyError, TypeError) as e:
        logger.error("generate_node 데이터 오류 error=%s", e, exc_info=True)
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.GENERATE_PARSE_ERROR,
            "error_message": f"이력서 생성 중 데이터 오류: {e}",
        }


async def evaluate_node(state: ResumeState) -> ResumeState:
    """이력서 평가 노드: 품질 평가 수행"""
    logger.info("evaluate_node 시작")

    resume_data = state["resume_data"]
    request = state["request"]
    session_id = state.get("session_id")

    try:
        evaluation = await evaluate_resume(
            resume_data=resume_data,
            position=request.position,
            session_id=session_id,
        )

        logger.info("evaluate_node 완료 result=%s", evaluation.result)

        return {
            **state,
            "evaluation": evaluation.result,
            "evaluation_feedback": evaluation.feedback,
        }

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        logger.warning("evaluate_node LLM API 오류, 평가 건너뜀 status=%d", status_code)
        return {
            **state,
            "evaluation": "pass",
            "evaluation_feedback": "",
        }

    except (ValueError, KeyError, TypeError) as e:
        logger.warning("evaluate_node 데이터 오류, 평가 건너뜀 error=%s", e)
        return {
            **state,
            "evaluation": "pass",
            "evaluation_feedback": "",
        }


def should_continue(state: ResumeState) -> Literal["generate", "end"]:
    """에러 상태 확인: 에러 있으면 종료, 없으면 다음 노드로"""
    if state.get("error_code"):
        logger.info("should_continue: 에러 발생, 종료")
        return "end"
    return "generate"


def should_evaluate(state: ResumeState) -> Literal["evaluate", "end"]:
    """에러 상태 확인: 에러 있으면 종료, 없으면 평가 노드로"""
    if state.get("error_code"):
        logger.info("should_evaluate: 에러 발생, 종료")
        return "end"
    return "evaluate"


def should_retry(state: ResumeState) -> Literal["generate", "end"]:
    """재시도 여부 결정: pass면 종료, fail이면 generate로 루프"""
    if state.get("error_code"):
        logger.info("should_retry: 에러 발생, 종료")
        return "end"

    evaluation = state.get("evaluation", "pass")
    retry_count = state.get("retry_count", 0)

    if evaluation == "pass":
        logger.info("should_retry: 평가 통과, 종료")
        return "end"

    if retry_count >= settings.workflow_max_retries:
        logger.warning("should_retry: 최대 재시도 도달, 종료")
        return "end"

    logger.info("should_retry: 재시도 필요 retry_count=%d", retry_count)
    return "generate"


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
    project_info: list[dict],
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
    logger.info("배치 처리 시작 total=%d batches=%d", len(project_info), len(batches))

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
