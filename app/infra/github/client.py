import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.resume.schemas import CommitDetail, CommitInfo, PRInfo

logger = get_logger(__name__)

GITHUB_API_BASE = "https://api.github.com"

_client = httpx.AsyncClient(timeout=settings.github_timeout)


async def close_client():
    """httpx 클라이언트 종료."""
    await _client.aclose()


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """GitHub URL에서 owner와 repo 추출.

    Args:
        repo_url: GitHub 레포지토리 URL

    Returns:
        (owner, repo) 튜플
    """
    parts = repo_url.rstrip("/").split("/")
    owner = parts[-2]
    repo = parts[-1].replace(".git", "")
    return owner, repo


async def get_commits(
    repo_url: str,
    token: str | None = None,
    author: str | None = None,
    per_page: int = 100,
) -> list[CommitInfo]:
    """레포지토리의 커밋 목록 조회.

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰 (공개 레포는 생략 가능)
        author: GitHub 유저네임 (해당 유저의 커밋만 필터링)
        per_page: 가져올 커밋 개수 (기본 100, 최대 100)

    Returns:
        커밋 목록 (sha, message, author 등 포함), merge 커밋 제외
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {"per_page": min(per_page, 100)}
    if author:
        params["author"] = author

    response = await _client.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    commits = [
        CommitInfo(
            sha=commit["sha"],
            message=commit["commit"]["message"],
            author=commit["commit"]["author"]["name"],
        )
        for commit in data
        if len(commit.get("parents", [])) < 2
    ]

    logger.info("커밋 조회 완료 repo=%s/%s count=%d", owner, repo, len(commits))
    return commits


async def get_commit_detail(repo_url: str, sha: str, token: str | None = None) -> CommitDetail:
    """개별 커밋의 상세 정보 (diff 포함) 조회.

    Args:
        repo_url: GitHub 레포지토리 URL
        sha: 커밋 SHA
        token: GitHub OAuth 토큰 (공개 레포는 생략 가능)

    Returns:
        커밋 상세 정보 (files 필드에 diff 포함)
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}"

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = await _client.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    logger.info("커밋 상세 조회 완료 repo=%s/%s sha=%s", owner, repo, sha[:7])
    return CommitDetail(
        sha=data["sha"],
        message=data["commit"]["message"],
        author=data["commit"]["author"]["name"],
        files=data.get("files", []),
    )


async def get_pulls(
    repo_url: str,
    token: str | None = None,
    author: str | None = None,
    per_page: int = 30,
) -> list[PRInfo]:
    """레포지토리의 Merged PR 목록 조회.

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰 (공개 레포는 생략 가능)
        author: GitHub 유저네임 (해당 유저의 PR만 필터링)
        per_page: 가져올 PR 개수 (기본 30)

    Returns:
        Merged PR 목록 (number, title, body, author, merged_at 포함)
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"

    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {"state": "closed", "per_page": min(per_page, 100)}

    response = await _client.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()

    prs = []
    for pr in data:
        if pr.get("merged_at") is None:
            continue
        if author and pr["user"]["login"].lower() != author.lower():
            continue
        prs.append(
            PRInfo(
                number=pr["number"],
                title=pr["title"],
                body=pr.get("body"),
                author=pr["user"]["login"],
                merged_at=pr["merged_at"],
                repo_url=repo_url,
            )
        )

    logger.info("PR 조회 완료 repo=%s/%s count=%d", owner, repo, len(prs))
    return prs
