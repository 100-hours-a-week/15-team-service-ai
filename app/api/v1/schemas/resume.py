"""이력서 API 스키마."""

import re

from pydantic import BaseModel, Field, field_validator

GITHUB_REPO_PATTERN = re.compile(r"^https://github\.com/[^/]+/[^/]+$")


class GenerateRequest(BaseModel):
    """이력서 생성 요청."""

    repo_urls: list[str] = Field(alias="repoUrls")
    position: str = Field(min_length=1)
    company: str | None = None
    github_token: str = Field(alias="githubToken")
    callback_url: str | None = Field(default=None, alias="callbackUrl")

    @field_validator("repo_urls")
    @classmethod
    def validate_repo_urls(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("최소 1개의 레포지토리 URL이 필요합니다")
        for url in v:
            if not GITHUB_REPO_PATTERN.match(url):
                raise ValueError(f"올바른 GitHub URL 형식이 아닙니다: {url}")
        return v

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("callback_url은 http:// 또는 https://로 시작해야 합니다")
        return v

    class Config:
        populate_by_name = True


class GenerateResponse(BaseModel):
    """이력서 생성 응답."""

    job_id: str = Field(alias="jobId")

    class Config:
        populate_by_name = True
        by_alias = True
