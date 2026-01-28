from app.core.logging import get_logger
from app.domain.resume.parsers import DEPENDENCY_FILES, parse_dependency_file
from app.domain.resume.schemas import RepoContext, ResumeRequest, UserStats
from app.infra.github.client import (
    get_files_content,
    get_project_info,
    get_repo_context,
    get_user_stats,
    parse_repo_url,
)

__all__ = [
    "collect_project_info",
    "collect_repo_contexts",
    "collect_user_stats",
]

logger = get_logger(__name__)

EXCLUDE_PATTERNS = [
    "test",
    "pytest",
    "junit",
    "mockito",
    "jest",
    "mocha",
    "vitest",
    "eslint",
    "prettier",
    "ruff",
    "black",
    "flake8",
    "mypy",
    "types-",
    "@types/",
    "pre-commit",
    "husky",
    "lint-staged",
]

PRIORITY_PATTERNS = [
    "fastapi",
    "flask",
    "django",
    "uvicorn",
    "pydantic",
    "sqlalchemy",
    "celery",
    "spring",
    "quarkus",
    "jpa",
    "hibernate",
    "lombok",
    "querydsl",
    "mapstruct",
    "react",
    "vue",
    "angular",
    "next",
    "nuxt",
    "express",
    "nestjs",
    "prisma",
    "typeorm",
    "redis",
    "kafka",
    "rabbitmq",
]


def _filter_and_sort_dependencies(deps: list[str]) -> list[str]:
    """의존성 필터링 및 우선순위 정렬

    Args:
        deps: 원본 의존성 리스트

    Returns:
        필터링되고 정렬된 의존성 리스트
    """
    filtered = []
    for dep in deps:
        dep_lower = dep.lower()
        should_exclude = any(pattern in dep_lower for pattern in EXCLUDE_PATTERNS)
        if not should_exclude:
            filtered.append(dep)

    def priority_key(dep: str) -> int:
        dep_lower = dep.lower()
        for i, pattern in enumerate(PRIORITY_PATTERNS):
            if pattern in dep_lower:
                return i
        return len(PRIORITY_PATTERNS)

    sorted_deps = sorted(filtered, key=priority_key)
    return sorted_deps


async def collect_project_info(request: ResumeRequest) -> list[dict]:
    """파일 목록 + 의존성 파일 기반으로 프로젝트 정보 수집.

    Args:
        request: 이력서 생성 요청

    Returns:
        프로젝트 정보 리스트
    """
    results = []

    for repo_url in request.repo_urls:
        _, repo_name = parse_repo_url(repo_url)

        try:
            project_info = await get_project_info(repo_url, request.github_token)
            file_tree = project_info["file_tree"]
            commits = project_info["commits"]
            pulls = project_info["pulls"]

            dependencies = await _parse_dependencies(repo_url, file_tree, request.github_token)
            messages = _format_messages(commits, pulls)

            results.append(
                {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "file_tree": _summarize_file_tree(file_tree),
                    "dependencies": dependencies,
                    "messages": messages,
                }
            )

            logger.info(
                "프로젝트 정보 수집 완료 repo=%s files=%d deps=%d messages=%d",
                repo_name,
                len(file_tree),
                len(dependencies),
                len(messages),
            )

        except Exception as e:
            logger.error("프로젝트 정보 수집 실패 repo=%s error=%s", repo_name, e)
            results.append(
                {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "file_tree": [],
                    "dependencies": [],
                    "messages": [],
                }
            )

    logger.info("전체 프로젝트 정보 수집 완료 count=%d", len(results))
    return results


def _summarize_file_tree(file_tree: list[str]) -> list[str]:
    """파일 트리를 디렉토리 구조 중심으로 요약.

    Args:
        file_tree: 전체 파일 경로 리스트

    Returns:
        주요 디렉토리와 파일 확장자 요약
    """
    dirs = set()
    extensions = set()

    for path in file_tree:
        parts = path.split("/")
        if len(parts) > 1:
            dirs.add(parts[0])
            if len(parts) > 2:
                dirs.add(f"{parts[0]}/{parts[1]}")

        if "." in path:
            ext = path.rsplit(".", 1)[-1]
            if len(ext) <= 5:
                extensions.add(ext)

    summary = []
    summary.extend(sorted(dirs)[:20])
    summary.append(f"extensions: {', '.join(sorted(extensions))}")

    return summary


async def _parse_dependencies(repo_url: str, file_tree: list[str], token: str | None) -> list[str]:
    """파일 트리에서 의존성 파일을 찾아 파싱.

    Args:
        repo_url: GitHub 레포지토리 URL
        file_tree: 파일 경로 리스트
        token: GitHub 토큰

    Returns:
        의존성 패키지 리스트
    """
    dependency_paths = []
    for file_path in file_tree:
        filename = file_path.split("/")[-1]
        if filename in DEPENDENCY_FILES:
            dependency_paths.append(file_path)

    if not dependency_paths:
        return []

    contents = await get_files_content(repo_url, dependency_paths, token)

    all_deps = []
    for file_path, content in contents.items():
        if not content:
            continue

        filename = file_path.split("/")[-1]
        parsed = parse_dependency_file(filename, content)
        deps = parsed.get("dependencies", [])
        dev_deps = parsed.get("devDependencies", [])
        all_deps.extend(deps)
        all_deps.extend(dev_deps)

    unique_deps = list(set(all_deps))
    filtered_deps = _filter_and_sort_dependencies(unique_deps)
    return filtered_deps


def _format_messages(commits: list, pulls: list) -> list[str]:
    """커밋과 PR 정보를 메시지 리스트로 포맷팅.

    Args:
        commits: CommitInfo 리스트
        pulls: PRInfoExtended 리스트

    Returns:
        메시지 리스트
    """
    messages = []

    for pr in pulls:
        msg = f"PR #{pr.number}: {pr.title}"
        msg += f" [커밋 {pr.commits_count}개, +{pr.additions}/-{pr.deletions}]"
        if pr.body:
            body_summary = pr.body[:500].replace("\n", " ")
            msg += f" - {body_summary}"
        messages.append(msg)

    for commit in commits:
        first_line = commit.message.split("\n")[0]
        messages.append(f"commit: {first_line}")

    return messages


async def collect_repo_contexts(request: ResumeRequest) -> dict[str, RepoContext]:
    """각 레포지토리의 컨텍스트 정보 수집.

    Args:
        request: 이력서 생성 요청

    Returns:
        레포 이름을 키로 하는 RepoContext 딕셔너리
    """
    contexts = {}

    for repo_url in request.repo_urls:
        _, repo_name = parse_repo_url(repo_url)

        try:
            context = await get_repo_context(repo_url, request.github_token)

            contexts[repo_name] = RepoContext(
                name=repo_name,
                languages=context["languages"],
                description=context["description"],
                topics=context["topics"],
                readme_summary=context["readme"],
            )
        except Exception as e:
            logger.warning("컨텍스트 수집 실패 repo=%s error=%s", repo_name, e)
            contexts[repo_name] = RepoContext(
                name=repo_name,
                languages={},
                description=None,
                topics=[],
                readme_summary=None,
            )

    logger.info("컨텍스트 수집 완료 repos=%d", len(contexts))
    return contexts


async def collect_user_stats(username: str, token: str | None) -> UserStats | None:
    """사용자 GitHub 통계 수집.

    Args:
        username: GitHub 유저네임
        token: GitHub OAuth 토큰

    Returns:
        사용자 통계 정보, 토큰 없거나 실패하면 None
    """
    if not token:
        logger.info("토큰 없음, 사용자 통계 수집 건너뜀 username=%s", username)
        return None

    try:
        stats = await get_user_stats(username, token)
        logger.info(
            "사용자 통계 수집 완료 username=%s commits=%d prs=%d issues=%d",
            username,
            stats.total_commits,
            stats.total_prs,
            stats.total_issues,
        )
        return stats
    except Exception as e:
        logger.warning("사용자 통계 수집 실패 username=%s error=%s", username, e)
        return None
