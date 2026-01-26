from typing import Any

from langchain_core.tools import tool

from app.core.logging import get_logger
from app.domain.resume.schemas import (
    AnalyzeExperiencesInput,
    CollectCommitDiffsInput,
    CollectPRDiffsInput,
    CollectRepoContextInput,
    DiffAnalysisOutput,
    EvaluateResumeInput,
    GenerateResumeInput,
    RepoContext,
    ResumeData,
    ResumeRequest,
)
from app.domain.resume.service import (
    _collect_diffs_for_repo,
    collect_pr_diffs_for_repo,
)
from app.domain.resume.service import (
    analyze_experiences as analyze_experiences_service,
)
from app.domain.resume.service import (
    collect_repo_contexts as collect_repo_contexts_service,
)
from app.infra.github.client import parse_repo_url
from app.infra.llm.client import (
    evaluate_resume as evaluate_resume_llm,
)
from app.infra.llm.client import (
    generate_resume as generate_resume_llm,
)

logger = get_logger(__name__)


@tool(args_schema=CollectPRDiffsInput)
async def collect_pr_diffs(
    repo_urls: list[str], github_token: str | None = None
) -> dict[str, Any]:
    """Collect merged PR diffs from GitHub repositories.

    Returns actual code changes from PRs, not just titles/bodies.
    If no PRs are found, returns empty and marks repo for commit fallback.
    """
    logger.info("Tool: collect_pr_diffs repo_count=%d", len(repo_urls))

    results = []
    repos_with_prs = []
    repos_without_prs = []

    for repo_url in repo_urls:
        _, repo_name = parse_repo_url(repo_url)
        try:
            pr_diffs = await collect_pr_diffs_for_repo(repo_url, github_token)
            if pr_diffs:
                results.extend(pr_diffs)
                repos_with_prs.append(repo_url)
                logger.info("PR diff 수집 성공 repo=%s count=%d", repo_name, len(pr_diffs))
            else:
                repos_without_prs.append(repo_url)
                logger.info("PR 없음 repo=%s", repo_name)
        except Exception as e:
            repos_without_prs.append(repo_url)
            logger.warning("PR 수집 실패 repo=%s error=%s", repo_name, e)

    return {
        "diffs": results,
        "repos_with_prs": repos_with_prs,
        "repos_without_prs": repos_without_prs,
        "total_diffs": len(results),
    }


@tool(args_schema=CollectCommitDiffsInput)
async def collect_commit_diffs(
    repo_urls: list[str], github_token: str | None = None, per_page: int = 30
) -> dict[str, Any]:
    """Collect commit diffs from GitHub repositories.

    Use this as a fallback when no PRs are available.
    Extracts meaningful code changes from recent commits.
    """
    logger.info("Tool: collect_commit_diffs repo_count=%d per_page=%d", len(repo_urls), per_page)

    results = []
    dummy_request = ResumeRequest(
        repo_urls=repo_urls,
        position="",
        github_token=github_token,
    )

    for repo_url in repo_urls:
        _, repo_name = parse_repo_url(repo_url)
        try:
            diffs = await _collect_diffs_for_repo(repo_url, dummy_request)
            results.extend(diffs)
            logger.info("커밋 수집 성공 repo=%s count=%d", repo_name, len(diffs))
        except Exception as e:
            logger.error("커밋 수집 실패 repo=%s error=%s", repo_name, e)

    return {
        "diffs": results,
        "total_diffs": len(results),
    }


@tool(args_schema=CollectRepoContextInput)
async def collect_repo_context(
    repo_urls: list[str], github_token: str | None = None
) -> dict[str, dict]:
    """Collect repository context information.

    Gathers languages, description, topics, and README summary for each repository.
    This context helps generate more accurate resumes.
    """
    logger.info("Tool: collect_repo_context repo_count=%d", len(repo_urls))

    dummy_request = ResumeRequest(
        repo_urls=repo_urls,
        position="",
        github_token=github_token,
    )

    contexts = await collect_repo_contexts_service(dummy_request)
    return {name: ctx.model_dump() for name, ctx in contexts.items()}


@tool(args_schema=AnalyzeExperiencesInput)
async def analyze_experiences(
    diffs: list[dict[str, str]], session_id: str | None = None
) -> list[dict]:
    """Analyze collected diffs to extract developer experiences.

    Groups diffs by repository and uses LLM to extract:
    - Technology stack used
    - Description of implementation

    Returns list of experiences that can be used for resume generation.
    """
    logger.info("Tool: analyze_experiences diff_count=%d", len(diffs))

    experiences = await analyze_experiences_service(diffs)
    return [exp.model_dump() for exp in experiences]


@tool(args_schema=GenerateResumeInput)
async def generate_resume(
    experiences: list[dict[str, Any]],
    position: str,
    repo_urls: list[str],
    repo_contexts: dict[str, dict] | None = None,
    feedback: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Generate a resume based on extracted experiences.

    Creates a structured resume with:
    - Overall tech stack
    - Project list with individual tech stacks and descriptions

    If feedback is provided, incorporates it to improve the resume.
    Output is in Korean.
    """
    logger.info("Tool: generate_resume position=%s exp_count=%d", position, len(experiences))

    exp_objects = [
        DiffAnalysisOutput(tech_stack=exp["tech_stack"], description=exp["description"])
        for exp in experiences
    ]

    ctx_objects = None
    if repo_contexts:
        ctx_objects = {
            name: RepoContext(**ctx)
            for name, ctx in repo_contexts.items()
        }

    resume = await generate_resume_llm(
        experiences=exp_objects,
        position=position,
        repo_urls=repo_urls,
        feedback=feedback,
        repo_contexts=ctx_objects,
        session_id=session_id,
    )

    return resume.model_dump()


@tool(args_schema=EvaluateResumeInput)
async def evaluate_resume(
    resume_data: dict[str, Any], position: str, session_id: str | None = None
) -> dict[str, str]:
    """Evaluate the quality of a generated resume.

    Checks for common quality issues:
    - Annotations or class names in tech_stack
    - Description length
    - Missing projects or tech_stack
    - Invalid tech_stack entries (API, infrastructure tools, AI models, etc.)

    Returns:
    - result: "pass" or "fail"
    - feedback: Explanation of issues (if fail)
    """
    logger.info("Tool: evaluate_resume position=%s", position)

    resume = ResumeData(**resume_data)
    evaluation = await evaluate_resume_llm(
        resume_data=resume,
        position=position,
        session_id=session_id,
    )

    return evaluation.model_dump()


def get_resume_tools() -> list:
    """에이전트용 툴 목록 반환."""
    return [
        collect_pr_diffs,
        collect_commit_diffs,
        collect_repo_context,
        analyze_experiences,
        generate_resume,
        evaluate_resume,
    ]
