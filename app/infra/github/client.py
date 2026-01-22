import httpx

from app.domain.resume.schemas import CommitDetail, CommitInfo


GITHUB_API_BASE = "https://api.github.com"


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
    token: str,
    author: str | None = None,
    per_page: int = 100,
) -> list[CommitInfo]:
    """레포지토리의 커밋 목록 조회.

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰
        author: GitHub 유저네임 (해당 유저의 커밋만 필터링)
        per_page: 가져올 커밋 개수 (기본 100, 최대 100)

    Returns:
        커밋 목록 (sha, message, author 등 포함), merge 커밋 제외
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    params = {"per_page": min(per_page, 100)}
    if author:
        params["author"] = author

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    # merge 커밋 제외 (부모가 2개 이상인 커밋)
    commits = [
        CommitInfo(
            sha=commit["sha"],
            message=commit["commit"]["message"],
            author=commit["commit"]["author"]["name"],
        )
        for commit in data
        if len(commit.get("parents", [])) < 2
    ]

    return commits


async def get_commit_detail(repo_url: str, sha: str, token: str) -> CommitDetail:
    """개별 커밋의 상세 정보 (diff 포함) 조회.

    Args:
        repo_url: GitHub 레포지토리 URL
        sha: 커밋 SHA
        token: GitHub OAuth 토큰

    Returns:
        커밋 상세 정보 (files 필드에 diff 포함)
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{sha}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

    return CommitDetail(
        sha=data["sha"],
        message=data["commit"]["message"],
        author=data["commit"]["author"]["name"],
        files=data.get("files", []),
    )
