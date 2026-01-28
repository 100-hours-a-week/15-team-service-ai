import asyncio

from app.core.logging import get_logger
from app.domain.resume.schemas import ResumeData, ResumeRequest
from app.domain.resume.service import (
    collect_project_info,
    collect_repo_contexts,
    collect_user_stats,
)
from app.infra.github.client import parse_repo_url
from app.infra.llm.client import evaluate_resume, generate_resume

logger = get_logger(__name__)

MAX_RETRIES = 2
BATCH_SIZE = 3


async def run_resume_agent(
    request: ResumeRequest,
    session_id: str | None = None,
) -> tuple[ResumeData | None, str | None]:
    """에이전트 기반 이력서 생성 워크플로우.

    Args:
        request: 이력서 생성 요청
        session_id: Langfuse 세션 ID

    Returns:
        resume_data, error_message 튜플
    """
    logger.info(
        "에이전트 시작 repos=%d position=%s session_id=%s",
        len(request.repo_urls),
        request.position,
        session_id,
    )

    try:
        project_info = await collect_project_info(request)
        if not project_info:
            return None, "프로젝트 정보 수집 실패"

        repo_contexts = await collect_repo_contexts(request)

        username, _ = parse_repo_url(request.repo_urls[0])
        user_stats = await collect_user_stats(username, request.github_token)

        resume_data = await _generate_and_evaluate(
            project_info=project_info,
            request=request,
            repo_contexts=repo_contexts,
            user_stats=user_stats,
            session_id=session_id,
        )

        return resume_data, None

    except Exception as e:
        logger.error("에이전트 실패 error=%s", e, exc_info=True)
        return None, str(e)


async def _generate_and_evaluate(
    project_info: list[dict],
    request: ResumeRequest,
    repo_contexts: dict,
    user_stats=None,
    session_id: str | None = None,
) -> ResumeData:
    """이력서 생성 및 평가.

    Args:
        project_info: collect_project_info의 반환값
        request: 이력서 생성 요청
        repo_contexts: 레포지토리 컨텍스트
        user_stats: 사용자 GitHub 통계
        session_id: Langfuse 세션 ID

    Returns:
        생성된 이력서 데이터
    """
    feedback = None

    for attempt in range(MAX_RETRIES):
        resume_data = await _generate_in_batches(
            project_info=project_info,
            request=request,
            repo_contexts=repo_contexts,
            user_stats=user_stats,
            feedback=feedback,
            session_id=session_id,
        )
        batch_count = _count_batches(project_info)
        logger.debug("이력서 생성 완료 attempt=%d batches=%d", attempt + 1, batch_count)

        evaluation = await evaluate_resume(
            resume_data=resume_data,
            position=request.position,
            session_id=session_id,
        )
        logger.debug("평가 완료 result=%s", evaluation.result)

        if evaluation.result == "pass":
            logger.debug("평가 통과")
            return resume_data

        feedback = evaluation.feedback
        if attempt == MAX_RETRIES - 1:
            logger.warning("최대 재시도 도달, 마지막 결과 반환")

    return resume_data


def _count_batches(project_info: list[dict]) -> int:
    """배치 개수 계산"""
    return (len(project_info) + BATCH_SIZE - 1) // BATCH_SIZE


async def _generate_in_batches(
    project_info: list[dict],
    request: ResumeRequest,
    repo_contexts: dict,
    user_stats=None,
    feedback: str | None = None,
    session_id: str | None = None,
) -> ResumeData:
    """프로젝트를 배치로 나누어 이력서 생성 후 병합.

    Args:
        project_info: 전체 프로젝트 정보 리스트
        request: 이력서 생성 요청
        repo_contexts: 레포지토리 컨텍스트
        user_stats: 사용자 GitHub 통계
        feedback: 이전 평가 피드백
        session_id: Langfuse 세션 ID

    Returns:
        병합된 이력서 데이터
    """
    if len(project_info) <= BATCH_SIZE:
        return await generate_resume(
            project_info=project_info,
            position=request.position,
            repo_urls=request.repo_urls,
            repo_contexts=repo_contexts,
            user_stats=user_stats,
            feedback=feedback,
            session_id=session_id,
        )

    batches = [project_info[i : i + BATCH_SIZE] for i in range(0, len(project_info), BATCH_SIZE)]
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
    """여러 ResumeData를 하나로 병합.

    Args:
        results: 배치별 생성 결과 리스트

    Returns:
        병합된 ResumeData
    """
    all_projects = []
    all_tech_stack = []

    for result in results:
        all_projects.extend(result.projects)
        all_tech_stack.extend(result.tech_stack)

    unique_tech_stack = list(dict.fromkeys(all_tech_stack))

    return ResumeData(
        tech_stack=unique_tech_stack,
        projects=all_projects,
    )
