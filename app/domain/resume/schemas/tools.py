from typing import Any

from pydantic import BaseModel, Field


class CollectPRDiffsInput(BaseModel):
    """PR 수집 Tool 입력."""

    repo_urls: list[str] = Field(description="GitHub repository URLs")
    github_token: str | None = Field(default=None, description="GitHub access token")


class CollectCommitDiffsInput(BaseModel):
    """커밋 수집 Tool 입력."""

    repo_urls: list[str] = Field(description="GitHub repository URLs")
    github_token: str | None = Field(default=None, description="GitHub access token")
    per_page: int = Field(default=30, description="Number of commits to fetch per repo")


class CollectRepoContextInput(BaseModel):
    """레포 컨텍스트 수집 Tool 입력."""

    repo_urls: list[str] = Field(description="GitHub repository URLs")
    github_token: str | None = Field(default=None, description="GitHub access token")


class AnalyzeExperiencesInput(BaseModel):
    """경험 분석 Tool 입력."""

    diffs: list[dict[str, str]] = Field(
        description="List of diffs with repo_name and diff_content"
    )
    session_id: str | None = Field(default=None, description="Langfuse session ID")


class GenerateResumeInput(BaseModel):
    """이력서 생성 Tool 입력."""

    experiences: list[dict[str, Any]] = Field(description="Extracted experiences")
    position: str = Field(description="Target job position")
    repo_urls: list[str] = Field(description="Repository URLs")
    repo_contexts: dict[str, dict] | None = Field(default=None, description="Repository context")
    feedback: str | None = Field(default=None, description="Previous evaluation feedback")
    session_id: str | None = Field(default=None, description="Langfuse session ID")


class EvaluateResumeInput(BaseModel):
    """이력서 평가 Tool 입력."""

    resume_data: dict[str, Any] = Field(description="Generated resume data")
    position: str = Field(description="Target job position")
    session_id: str | None = Field(default=None, description="Langfuse session ID")
