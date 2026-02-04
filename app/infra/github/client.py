import asyncio
import base64
import re

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.resume.schemas import (
    CommitInfo,
    PRInfoExtended,
    UserStats,
)

logger = get_logger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

GITHUB_URL_PATTERN = re.compile(r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)")
FILE_PATH_PATTERN = re.compile(r"^[\w\-./]+$")

DANGEROUS_PATH_PARTS = frozenset(
    {
        ".git",
        ".github",
        ".env",
        "secrets",
        "credentials",
        ".aws",
        ".ssh",
        "private",
    }
)

_client = httpx.AsyncClient(timeout=settings.github_timeout)
_request_semaphore = asyncio.Semaphore(settings.github_max_concurrent_requests)


def _get_headers(token: str | None = None) -> dict[str, str]:
    """GitHub API 요청 헤더 생성

    Args:
        token: GitHub OAuth 토큰

    Returns:
        HTTP 헤더 딕셔너리
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def close_client():
    """httpx 클라이언트 종료"""
    await _client.aclose()


async def get_authenticated_user(token: str) -> tuple[str | None, str | None]:
    """토큰으로 인증된 사용자의 username과 name 조회

    GitHub API: GET /user 엔드포인트 사용

    Args:
        token: GitHub OAuth 토큰

    Returns:
        username, name 튜플, 실패 시 None, None
    """
    url = f"{GITHUB_API_BASE}/user"

    try:
        response = await _client.get(url, headers=_get_headers(token))
        response.raise_for_status()
        data = response.json()
        username = data.get("login")
        name = data.get("name")
        logger.info("인증된 사용자 조회 완료", username=username, name=name)
        return username, name
    except httpx.HTTPStatusError as e:
        logger.warning("인증된 사용자 조회 실패", status=e.response.status_code)
        return None, None
    except Exception as e:
        logger.warning("인증된 사용자 조회 실패", error=type(e).__name__)
        return None, None


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    """GitHub URL에서 owner와 repo 추출

    Args:
        repo_url: GitHub 레포지토리 URL

    Returns:
        owner, repo 튜플

    Raises:
        ValueError: 유효하지 않은 GitHub URL인 경우
    """
    match = GITHUB_URL_PATTERN.search(repo_url)
    if not match:
        raise ValueError(f"유효하지 않은 GitHub URL: {repo_url}")
    owner = match.group(1)
    repo = match.group(2).replace(".git", "")
    return owner, repo


def _sanitize_file_path(path: str) -> str:
    """파일 경로 검증

    Args:
        path: 파일 경로

    Returns:
        검증된 파일 경로

    Raises:
        ValueError: 유효하지 않은 파일 경로인 경우
    """
    if ".." in path:
        raise ValueError(f"경로 순회 차단: {path}")

    if path.startswith("/"):
        raise ValueError(f"절대 경로 차단: {path}")

    path_parts = path.lower().split("/")
    for part in path_parts:
        if part in DANGEROUS_PATH_PARTS:
            raise ValueError(f"민감한 경로 차단: {path}")

    if not FILE_PATH_PATTERN.match(path):
        raise ValueError(f"유효하지 않은 파일 경로: {path}")

    return path


async def get_commits(
    repo_url: str,
    token: str | None = None,
    author_name: str | None = None,
    per_page: int = 100,
) -> list[CommitInfo]:
    """레포지토리 커밋 목록 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰
        author_name: Git author name, 커밋 필터링에 사용
        per_page: 가져올 커밋 개수

    Returns:
        커밋 목록, merge 커밋 제외
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits"

    params = {"per_page": min(per_page, 100)}

    response = await _client.get(url, headers=_get_headers(token), params=params)
    response.raise_for_status()
    data = response.json()

    commits = []
    for commit in data:
        if len(commit.get("parents", [])) >= 2:
            continue
        commit_author = commit["commit"]["author"]["name"]
        if author_name and author_name.lower() not in commit_author.lower():
            continue
        commits.append(
            CommitInfo(
                sha=commit["sha"],
                message=commit["commit"]["message"],
                author=commit_author,
            )
        )

    logger.info("커밋 조회 완료", repo=f"{owner}/{repo}", count=len(commits))
    return commits


async def get_repo_languages(repo_url: str, token: str | None = None) -> dict[str, int]:
    """레포지토리 언어 비율 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰

    Returns:
        언어별 바이트 수 딕셔너리
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/languages"

    response = await _client.get(url, headers=_get_headers(token))
    response.raise_for_status()

    logger.info("언어 조회 완료", repo=f"{owner}/{repo}")
    return response.json()


async def get_repo_info(repo_url: str, token: str | None = None) -> dict:
    """레포지토리 메타데이터 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰

    Returns:
        description과 topics를 포함한 딕셔너리
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"

    response = await _client.get(url, headers=_get_headers(token))
    response.raise_for_status()
    data = response.json()

    logger.info("레포 정보 조회 완료", repo=f"{owner}/{repo}")
    return {
        "description": data.get("description"),
        "topics": data.get("topics", []),
    }


async def get_repo_readme(repo_url: str, token: str | None = None) -> str | None:
    """레포지토리 README 내용 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰

    Returns:
        README 내용 앞 2000자, 없으면 None
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"

    try:
        response = await _client.get(url, headers=_get_headers(token))
        response.raise_for_status()
        data = response.json()

        content = base64.b64decode(data["content"]).decode("utf-8")
        logger.info("README 조회 완료", repo=f"{owner}/{repo}")
        return content[: settings.readme_max_length_github]
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info("README 없음", repo=f"{owner}/{repo}")
            return None
        raise


async def get_repo_tree(repo_url: str, token: str | None = None) -> list[str]:
    """레포지토리 전체 파일 목록 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰

    Returns:
        파일 경로 리스트

    Raises:
        httpx.HTTPStatusError: GitHub API 호출 실패 시
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/HEAD"

    params = {"recursive": "1"}

    response = await _client.get(url, headers=_get_headers(token), params=params)
    response.raise_for_status()
    data = response.json()

    files = [item["path"] for item in data.get("tree", []) if item["type"] == "blob"]
    logger.info("파일 트리 조회 완료", repo=f"{owner}/{repo}", files=len(files))
    return files


async def get_file_content(repo_url: str, path: str, token: str | None = None) -> str | None:
    """특정 파일 내용 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        path: 파일 경로
        token: GitHub OAuth 토큰

    Returns:
        파일 내용 문자열, 없거나 바이너리면 None
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"

    try:
        response = await _client.get(url, headers=_get_headers(token))
        response.raise_for_status()
        data = response.json()

        if data.get("encoding") != "base64":
            return None

        content = base64.b64decode(data["content"]).decode("utf-8")
        logger.info("파일 조회 완료", repo=f"{owner}/{repo}", path=path)
        return content
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.info("파일 없음", repo=f"{owner}/{repo}", path=path)
            return None
        logger.warning("파일 조회 실패", repo=f"{owner}/{repo}", path=path, error=type(e).__name__)
        return None
    except UnicodeDecodeError:
        logger.info("바이너리 파일 스킵", repo=f"{owner}/{repo}", path=path)
        return None


async def _graphql_query(query: str, variables: dict, token: str) -> dict:
    """GraphQL 쿼리 실행

    Args:
        query: GraphQL 쿼리 문자열
        variables: 쿼리 변수
        token: GitHub OAuth 토큰

    Returns:
        GraphQL 응답의 data 필드

    Raises:
        ValueError: GraphQL 에러 발생 시
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    response = await _client.post(
        GITHUB_GRAPHQL_URL,
        headers=headers,
        json={"query": query, "variables": variables},
    )
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        error_count = len(data["errors"])
        for i, error in enumerate(data["errors"], 1):
            error_message = error.get("message", "알 수 없는 에러")
            error_type = error.get("type", "UNKNOWN")
            error_path = error.get("path", [])
            logger.warning(
                "GraphQL 에러",
                index=f"{i}/{error_count}",
                type=error_type,
                message=error_message,
                path=error_path,
            )
        raise ValueError(f"GraphQL 요청 실패: {error_count}개의 에러 발생")

    return data["data"]


async def get_repo_context_graphql(repo_url: str, token: str) -> dict:
    """GraphQL로 레포지토리 컨텍스트 정보 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰

    Returns:
        languages, description, topics, readme를 포함한 딕셔너리
    """
    owner, repo = parse_repo_url(repo_url)

    query = """
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        description
        repositoryTopics(first: 10) {
          nodes { topic { name } }
        }
        languages(first: 10) {
          edges { size node { name } }
        }
        object(expression: "HEAD:README.md") {
          ... on Blob { text }
        }
      }
    }
    """

    data = await _graphql_query(query, {"owner": owner, "repo": repo}, token)
    repository = data["repository"]

    languages = {}
    for edge in repository.get("languages", {}).get("edges", []):
        languages[edge["node"]["name"]] = edge["size"]

    topics = []
    for node in repository.get("repositoryTopics", {}).get("nodes", []):
        if node and node.get("topic"):
            topics.append(node["topic"]["name"])

    readme_obj = repository.get("object")
    readme = (
        readme_obj.get("text")[: settings.readme_max_length_github]
        if readme_obj and readme_obj.get("text")
        else None
    )

    logger.info("GraphQL 컨텍스트 조회 완료", repo=f"{owner}/{repo}")
    return {
        "languages": languages,
        "description": repository.get("description"),
        "topics": topics,
        "readme": readme,
    }


async def get_project_info_graphql(
    repo_url: str,
    token: str,
    author: str | None = None,
    author_name: str | None = None,
    commits_count: int = 50,
    prs_count: int = 50,
) -> dict:
    """GraphQL로 커밋과 PR 목록 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰
        author: GitHub 유저네임, PR 필터링에 사용
        author_name: Git author name, 커밋 필터링에 사용
        commits_count: 가져올 커밋 개수
        prs_count: 가져올 PR 개수

    Returns:
        commits, pulls를 포함한 딕셔너리
    """
    owner, repo = parse_repo_url(repo_url)

    query = """
    query($owner: String!, $repo: String!, $commitsCount: Int!, $prsCount: Int!) {
      repository(owner: $owner, name: $repo) {
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: $commitsCount) {
                nodes {
                  oid
                  message
                  author { name }
                  parents { totalCount }
                }
              }
            }
          }
        }
        pullRequests(
          states: MERGED
          first: $prsCount
          orderBy: {field: UPDATED_AT, direction: DESC}
        ) {
          nodes {
            number
            title
            body
            author { login }
            mergedAt
            additions
            deletions
            commits { totalCount }
          }
        }
      }
    }
    """

    variables = {
        "owner": owner,
        "repo": repo,
        "commitsCount": commits_count,
        "prsCount": prs_count,
    }

    data = await _graphql_query(query, variables, token)
    repository = data["repository"]

    commits = []
    branch_ref = repository.get("defaultBranchRef")
    if branch_ref and branch_ref.get("target"):
        history = branch_ref["target"].get("history", {})
        for node in history.get("nodes", []):
            if node.get("parents", {}).get("totalCount", 0) < 2:
                commit_author = node["author"]["name"] if node.get("author") else "Unknown"
                if author_name and author_name.lower() not in commit_author.lower():
                    continue
                commits.append(
                    CommitInfo(
                        sha=node["oid"],
                        message=node["message"],
                        author=commit_author,
                    )
                )

    pulls = []
    for pr_node in repository.get("pullRequests", {}).get("nodes", []):
        if not pr_node:
            continue
        pr_author = pr_node.get("author", {}).get("login", "")
        if author and pr_author.lower() != author.lower():
            continue
        pulls.append(
            PRInfoExtended(
                number=pr_node["number"],
                title=pr_node["title"],
                body=pr_node.get("body"),
                author=pr_author,
                merged_at=pr_node.get("mergedAt"),
                repo_url=repo_url,
                commits_count=pr_node.get("commits", {}).get("totalCount", 0),
                additions=pr_node.get("additions", 0),
                deletions=pr_node.get("deletions", 0),
            )
        )

    logger.info(
        "GraphQL 프로젝트 정보 조회 완료",
        repo=f"{owner}/{repo}",
        commits=len(commits),
        prs=len(pulls),
    )
    return {
        "commits": commits,
        "pulls": pulls,
    }


async def get_files_content_graphql(
    repo_url: str,
    paths: list[str],
    token: str,
) -> dict[str, str | None]:
    """GraphQL로 여러 파일 내용을 한 번에 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        paths: 파일 경로 리스트
        token: GitHub OAuth 토큰

    Returns:
        파일 경로를 키로, 내용을 값으로 하는 딕셔너리
    """
    if not paths:
        return {}

    owner, repo = parse_repo_url(repo_url)

    file_aliases = []
    for i, path in enumerate(paths):
        safe_path = _sanitize_file_path(path)
        alias = f'file{i}: object(expression: "HEAD:{safe_path}") {{ ... on Blob {{ text }} }}'
        file_aliases.append(alias)

    query = f"""
    query($owner: String!, $repo: String!) {{
      repository(owner: $owner, name: $repo) {{
        {chr(10).join(file_aliases)}
      }}
    }}
    """

    data = await _graphql_query(query, {"owner": owner, "repo": repo}, token)
    repository = data["repository"]

    result = {}
    for i, path in enumerate(paths):
        file_obj = repository.get(f"file{i}")
        if file_obj and file_obj.get("text"):
            result[path] = file_obj["text"]
        else:
            result[path] = None

    logger.info("GraphQL 파일 조회 완료", repo=f"{owner}/{repo}", files=len(paths))
    return result


async def get_files_content(
    repo_url: str,
    paths: list[str],
    token: str | None = None,
) -> dict[str, str | None]:
    """여러 파일 내용 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        paths: 파일 경로 리스트
        token: GitHub OAuth 토큰

    Returns:
        파일 경로를 키로, 내용을 값으로 하는 딕셔너리
    """
    if not paths:
        return {}

    async def fetch_with_limit(path: str) -> tuple[str, str | None]:
        async with _request_semaphore:
            content = await get_file_content(repo_url, path, token)
            return path, content

    result: dict[str, str | None] = {}
    paths_to_fetch: list[str] = paths

    if token:
        try:
            graphql_result = await get_files_content_graphql(repo_url, paths, token)
            result.update(graphql_result)
            paths_to_fetch = [p for p, content in graphql_result.items() if content is None]

            if paths_to_fetch:
                logger.info("GraphQL 부분 실패, REST 재시도", count=len(paths_to_fetch))
        except Exception as e:
            logger.warning("GraphQL 파일 조회 실패, REST 폴백", error=type(e).__name__)

    if paths_to_fetch:
        tasks = [fetch_with_limit(path) for path in paths_to_fetch]
        rest_results = await asyncio.gather(*tasks)
        for path, content in rest_results:
            result[path] = content

    return result


async def get_project_info(
    repo_url: str,
    token: str | None = None,
    author: str | None = None,
    author_name: str | None = None,
    commits_count: int = 50,
    prs_count: int = 50,
) -> dict:
    """프로젝트 정보 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰
        author: GitHub 유저네임, PR 필터링에 사용
        author_name: Git author name, 커밋 필터링에 사용
        commits_count: 가져올 커밋 개수
        prs_count: 가져올 PR 개수

    Returns:
        file_tree, commits, pulls를 포함한 딕셔너리
    """
    file_tree = await get_repo_tree(repo_url, token)

    if token:
        try:
            graphql_data = await get_project_info_graphql(
                repo_url, token, author, author_name, commits_count, prs_count
            )
            return {
                "file_tree": file_tree,
                "commits": graphql_data["commits"],
                "pulls": graphql_data["pulls"],
            }
        except Exception as e:
            logger.warning("GraphQL 프로젝트 정보 조회 실패, REST 폴백", error=type(e).__name__)

    commits = await get_commits(repo_url, token, author_name, commits_count)
    pulls = await get_pulls_extended(repo_url, token, author, prs_count)

    return {
        "file_tree": file_tree,
        "commits": commits,
        "pulls": pulls,
    }


async def get_repo_context(repo_url: str, token: str | None = None) -> dict:
    """레포지토리 컨텍스트 정보 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰

    Returns:
        languages, description, topics, readme를 포함한 딕셔너리
    """
    if token:
        try:
            return await get_repo_context_graphql(repo_url, token)
        except Exception as e:
            logger.warning("GraphQL 컨텍스트 조회 실패, REST 폴백", error=type(e).__name__)

    languages = await get_repo_languages(repo_url, token)
    info = await get_repo_info(repo_url, token)
    readme = await get_repo_readme(repo_url, token)

    return {
        "languages": languages,
        "description": info.get("description"),
        "topics": info.get("topics", []),
        "readme": readme,
    }


async def get_user_stats(username: str, token: str) -> UserStats:
    """사용자 GitHub 통계 조회

    Args:
        username: GitHub 유저네임
        token: GitHub OAuth 토큰

    Returns:
        사용자 통계 정보
    """
    query = """
    query($username: String!) {
      user(login: $username) {
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
        }
      }
    }
    """
    data = await _graphql_query(query, {"username": username}, token)
    user = data["user"]
    contrib = user["contributionsCollection"]

    logger.info("사용자 통계 조회 완료", username=username)
    return UserStats(
        total_commits=contrib["totalCommitContributions"],
        total_prs=contrib["totalPullRequestContributions"],
        total_issues=contrib["totalIssueContributions"],
    )


async def get_pulls_extended(
    repo_url: str,
    token: str | None = None,
    author: str | None = None,
    per_page: int = 30,
) -> list[PRInfoExtended]:
    """레포지토리 Merged PR 목록 조회

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰
        author: GitHub 유저네임
        per_page: 가져올 PR 개수

    Returns:
        확장된 PR 목록
    """
    owner, repo = parse_repo_url(repo_url)
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls"

    params = {"state": "closed", "per_page": min(per_page, 100)}

    response = await _client.get(url, headers=_get_headers(token), params=params)
    response.raise_for_status()
    data = response.json()

    merged_prs = [
        pr
        for pr in data
        if pr.get("merged_at") is not None
        and (not author or pr["user"]["login"].lower() == author.lower())
    ]

    async def fetch_detail_with_limit(pr_number: int) -> dict:
        async with _request_semaphore:
            return await _get_pull_detail(owner, repo, pr_number, token)

    tasks = [fetch_detail_with_limit(pr["number"]) for pr in merged_prs]
    details = await asyncio.gather(*tasks)

    prs = [
        PRInfoExtended(
            number=pr["number"],
            title=pr["title"],
            body=pr.get("body"),
            author=pr["user"]["login"],
            merged_at=pr["merged_at"],
            repo_url=repo_url,
            commits_count=detail["commits"],
            additions=detail["additions"],
            deletions=detail["deletions"],
        )
        for pr, detail in zip(merged_prs, details, strict=True)
    ]

    logger.info("PR 확장 조회 완료", repo=f"{owner}/{repo}", count=len(prs))
    return prs


async def _get_pull_detail(
    owner: str, repo: str, pull_number: int, token: str | None = None
) -> dict:
    """개별 PR 상세 정보 조회

    Args:
        owner: 레포지토리 소유자
        repo: 레포지토리 이름
        pull_number: PR 번호
        token: GitHub OAuth 토큰

    Returns:
        commits, additions, deletions 포함 딕셔너리
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pull_number}"
    response = await _client.get(url, headers=_get_headers(token))
    response.raise_for_status()
    data = response.json()

    return {
        "commits": data.get("commits", 0),
        "additions": data.get("additions", 0),
        "deletions": data.get("deletions", 0),
    }
