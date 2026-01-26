from typing import Any

from app.core.logging import get_logger
from app.domain.resume.schemas import ResumeData, ResumeRequest
from app.domain.resume.tools import (
    analyze_experiences,
    collect_commit_diffs,
    collect_pr_diffs,
    collect_repo_context,
    evaluate_resume,
    generate_resume,
)

logger = get_logger(__name__)

MAX_RETRIES = 2


async def run_resume_agent(
    request: ResumeRequest,
    session_id: str | None = None,
) -> tuple[ResumeData | None, str | None]:
    """에이전트 기반 이력서 생성 워크플로우.

    Args:
        request: 이력서 생성 요청
        session_id: Langfuse 세션 ID

    Returns:
        (resume_data, error_message) 튜플
    """
    logger.info(
        "에이전트 시작 repos=%d position=%s session_id=%s",
        len(request.repo_urls),
        request.position,
        session_id,
    )

    try:
        collected_diffs = await _collect_data(request)
        if not collected_diffs:
            return None, "데이터 수집 실패: PR과 커밋 모두 없음"

        repo_contexts = await _collect_contexts(request)

        experiences = await _analyze_data(collected_diffs, session_id)
        if not experiences:
            return None, "경험 분석 실패: 추출된 경험 없음"

        resume_data = await _generate_and_evaluate(
            experiences=experiences,
            request=request,
            repo_contexts=repo_contexts,
            session_id=session_id,
        )

        return resume_data, None

    except Exception as e:
        logger.error("에이전트 실패 error=%s", e)
        return None, str(e)


async def _collect_data(request: ResumeRequest) -> list[dict]:
    """PR 우선 수집, PR 없는 레포만 커밋 폴백."""
    collected_diffs: list[dict] = []

    pr_result = await collect_pr_diffs.ainvoke({
        "repo_urls": request.repo_urls,
        "github_token": request.github_token,
    })
    collected_diffs.extend(pr_result["diffs"])
    repos_without_prs = pr_result.get("repos_without_prs", [])
    logger.info(
        "PR diff 수집 완료 diffs=%d repos_without_prs=%d",
        len(pr_result["diffs"]),
        len(repos_without_prs),
    )

    if repos_without_prs:
        commit_result = await collect_commit_diffs.ainvoke({
            "repo_urls": repos_without_prs,
            "github_token": request.github_token,
        })
        collected_diffs.extend(commit_result["diffs"])
        logger.info("커밋 폴백 완료 diffs=%d", len(commit_result["diffs"]))

    logger.info("데이터 수집 완료 total_diffs=%d", len(collected_diffs))
    return collected_diffs


async def _collect_contexts(request: ResumeRequest) -> dict[str, dict]:
    """레포지토리 컨텍스트 수집."""
    context_result = await collect_repo_context.ainvoke({
        "repo_urls": request.repo_urls,
        "github_token": request.github_token,
    })
    logger.info("컨텍스트 수집 완료 repos=%d", len(context_result))
    return context_result


async def _analyze_data(
    diffs: list[dict], session_id: str | None = None
) -> list[dict[str, Any]]:
    """diff 분석하여 경험 추출."""
    experiences = await analyze_experiences.ainvoke({
        "diffs": diffs,
        "session_id": session_id,
    })
    logger.info("경험 분석 완료 count=%d", len(experiences))
    return experiences


async def _generate_and_evaluate(
    experiences: list[dict[str, Any]],
    request: ResumeRequest,
    repo_contexts: dict[str, dict],
    session_id: str | None = None,
) -> ResumeData:
    """이력서 생성 및 평가 (재시도 포함)."""
    feedback = None

    for attempt in range(MAX_RETRIES):
        resume_result = await generate_resume.ainvoke({
            "experiences": experiences,
            "position": request.position,
            "repo_urls": request.repo_urls,
            "repo_contexts": repo_contexts,
            "feedback": feedback,
            "session_id": session_id,
        })
        logger.info("이력서 생성 완료 attempt=%d", attempt + 1)

        eval_result = await evaluate_resume.ainvoke({
            "resume_data": resume_result,
            "position": request.position,
            "session_id": session_id,
        })
        logger.info(
            "평가 완료 result=%s feedback=%s",
            eval_result["result"],
            eval_result.get("feedback"),
        )

        if eval_result["result"] == "pass":
            logger.info("평가 통과")
            return ResumeData(**resume_result)

        feedback = eval_result.get("feedback")
        if attempt == MAX_RETRIES - 1:
            logger.warning("최대 재시도 도달, 마지막 결과 반환")

    return ResumeData(**resume_result)
