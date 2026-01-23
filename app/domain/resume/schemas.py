from typing import TypedDict

from pydantic import BaseModel


class CommitInfo(BaseModel):
    """커밋 기본 정보."""

    sha: str
    message: str
    author: str


class CommitDetail(BaseModel):
    """커밋 상세 정보."""

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


class DiffAnalysisOutput(BaseModel):
    """diff 분석 LLM 출력 (단일)."""

    tech_stack: list[str]
    description: str


class DiffBatchOutput(BaseModel):
    """diff 배치 분석 LLM 출력."""

    experiences: list[DiffAnalysisOutput]


class ProjectInfo(BaseModel):
    """프로젝트 정보."""

    name: str
    repo_url: str
    description: str


class ResumeData(BaseModel):
    """생성된 이력서 데이터."""

    tech_stack: list[str]
    projects: list[ProjectInfo]


class EvaluationOutput(BaseModel):
    """이력서 평가 LLM 출력."""

    result: str
    feedback: str


class ResumeState(TypedDict, total=False):
    """LangGraph 워크플로우 상태."""

    request: ResumeRequest
    job_id: str
    collected_data: list[dict]
    experiences: list[DiffAnalysisOutput]
    resume_data: ResumeData
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str
