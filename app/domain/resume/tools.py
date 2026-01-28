from typing import Any

from langchain_core.tools import tool

from app.core.logging import get_logger
from app.domain.resume.schemas import (
    CollectProjectInfoInput,
    CollectRepoContextInput,
    EvaluateResumeInput,
    GenerateResumeInput,
    RepoContext,
    ResumeData,
    ResumeRequest,
)
from app.domain.resume.service import (
    collect_project_info as collect_project_info_service,
)
from app.domain.resume.service import (
    collect_repo_contexts as collect_repo_contexts_service,
)
from app.infra.llm.client import (
    evaluate_resume as evaluate_resume_llm,
)
from app.infra.llm.client import (
    generate_resume as generate_resume_llm,
)

logger = get_logger(__name__)


@tool(args_schema=CollectProjectInfoInput)
async def collect_project_info(
    repo_urls: list[str], github_token: str | None = None
) -> dict[str, Any]:
    """Collect project information from GitHub repositories.

    Gathers file structure, dependencies, and PR/commit messages.
    This replaces the old diff-based collection approach.
    """
    logger.info("Tool: collect_project_info repo_count=%d", len(repo_urls))

    request = ResumeRequest(
        repo_urls=repo_urls,
        position="",
        github_token=github_token,
    )

    project_info = await collect_project_info_service(request)

    return {
        "project_info": project_info,
        "total_projects": len(project_info),
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

    request = ResumeRequest(
        repo_urls=repo_urls,
        position="",
        github_token=github_token,
    )

    contexts = await collect_repo_contexts_service(request)
    return {name: ctx.model_dump() for name, ctx in contexts.items()}


@tool(args_schema=GenerateResumeInput)
async def generate_resume(
    project_info: list[dict[str, Any]],
    position: str,
    repo_urls: list[str],
    repo_contexts: dict[str, dict] | None = None,
    feedback: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Generate a resume based on project information.

    Creates a structured resume with:
    - Overall tech stack
    - Project list with individual tech stacks and descriptions

    Uses file structure, dependencies, and PR/commit messages to understand
    what technologies were used and what was implemented.
    """
    logger.info("Tool: generate_resume position=%s projects=%d", position, len(project_info))

    ctx_objects = None
    if repo_contexts:
        ctx_objects = {name: RepoContext(**ctx) for name, ctx in repo_contexts.items()}

    resume = await generate_resume_llm(
        project_info=project_info,
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
    - Invalid tech_stack entries

    Returns:
    - result: "pass" or "fail"
    - feedback: Explanation of issues
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
    """에이전트용 툴 목록 반환"""
    return [
        collect_project_info,
        collect_repo_context,
        generate_resume,
        evaluate_resume,
    ]
