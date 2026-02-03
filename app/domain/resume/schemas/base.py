from typing import Literal, TypedDict

from pydantic import BaseModel

from app.domain.resume.schemas.github import RepoContext, UserStats


class ResumeRequest(BaseModel):
    """이력서 생성 요청"""

    repo_urls: list[str]
    position: str
    company: str | None = None
    github_token: str | None = None
    callback_url: str | None = None


class SkippedRepo(BaseModel):
    """스킵된 레포지토리 정보"""

    name: str
    reason: Literal["empty", "no_contribution", "error"]


class ProjectInfo(BaseModel):
    """프로젝트 정보"""

    name: str
    repo_url: str
    description: str
    tech_stack: list[str]


class ResumeData(BaseModel):
    """생성된 이력서 데이터"""

    projects: list[ProjectInfo]


class EvaluationOutput(BaseModel):
    """이력서 평가 LLM 출력"""

    result: Literal["pass", "fail"]
    violated_rule: int | None = None
    violated_item: str | None = None
    feedback: str


class ResumeState(TypedDict, total=False):
    """LangGraph 워크플로우 상태"""

    request: ResumeRequest
    job_id: str
    session_id: str | None
    project_info: list[dict]
    repo_contexts: dict[str, RepoContext]
    user_stats: UserStats | None
    resume_data: ResumeData
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str
