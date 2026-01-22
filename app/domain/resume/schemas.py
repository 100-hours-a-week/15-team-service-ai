from typing import TypedDict

from pydantic import BaseModel


class CommitInfo(BaseModel):
    """커밋 기본 정보."""

    sha: str
    message: str
    author: str


class CommitDetail(BaseModel):
    """커밋 상세 정보 (diff 포함)."""

    sha: str
    message: str
    author: str
    files: list[dict]


class ResumeRequest(BaseModel):
    """이력서 생성 요청."""

    repo_urls: list[str]
    position: str
    company: str | None = None
    github_token: str
    callback_url: str


class ProjectInfo(BaseModel):
    """프로젝트 정보."""

    name: str
    repo_url: str
    description: str


class ResumeData(BaseModel):
    """생성된 이력서 데이터."""

    tech_stack: list[str]
    projects: list[ProjectInfo]


class ResumeState(TypedDict, total=False):
    """LangGraph 워크플로우 상태."""

    request: ResumeRequest
    job_id: str
    collected_data: list[CommitDetail]
    resume_data: ResumeData
    evaluation: str
    retry_count: int
