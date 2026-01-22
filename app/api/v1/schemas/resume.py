"""이력서 API 스키마."""

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """이력서 생성 요청."""

    repo_urls: list[str] = Field(alias="repoUrls")
    position: str
    company: str | None = None
    github_token: str = Field(alias="githubToken")
    callback_url: str | None = Field(default=None, alias="callbackUrl")

    class Config:
        populate_by_name = True


class GenerateResponse(BaseModel):
    """이력서 생성 응답."""

    job_id: str = Field(alias="jobId")

    class Config:
        populate_by_name = True
        by_alias = True
