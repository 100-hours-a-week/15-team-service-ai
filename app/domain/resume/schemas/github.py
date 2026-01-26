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


class PRInfo(BaseModel):
    """PR 기본 정보."""

    number: int
    title: str
    body: str | None
    author: str
    merged_at: str
    repo_url: str


class RepoContext(BaseModel):
    """레포지토리 컨텍스트 정보."""

    name: str
    languages: dict[str, int]
    description: str | None
    topics: list[str]
    readme_summary: str | None
