from typing import Literal, TypedDict

from pydantic import BaseModel

from app.domain.resume.schemas.github import RepoContext


class ResumeRequest(BaseModel):
    """이력서 생성 요청."""

    repo_urls: list[str]
    position: str
    company: str | None = None
    github_token: str | None = None
    callback_url: str | None = None


class ProjectInfo(BaseModel):
    """프로젝트 정보."""

    name: str
    repo_url: str
    description: str
    tech_stack: list[str]


class ResumeData(BaseModel):
    """생성된 이력서 데이터."""

    tech_stack: list[str]
    projects: list[ProjectInfo]


class EvaluationOutput(BaseModel):
    """이력서 평가 LLM 출력."""

    result: Literal["pass", "fail"]
    feedback: str


class ResumeState(TypedDict, total=False):
    """LangGraph 워크플로우 상태."""

    request: ResumeRequest
    job_id: str
    project_info: list[dict]
    repo_contexts: dict[str, RepoContext]
    resume_data: ResumeData
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str
