import asyncio
import re

import httpx

from app.core.context import github_mock_var
from app.core.logging import get_logger
from app.domain.resume.constants import (
    BACKEND_TECHS,
    EXCLUDED_TECHS,
    FRONTEND_TECHS,
    POSITION_TECH_MAP,
    POSITION_VALIDATION_RULES,
)
from app.domain.resume.parsers import DEPENDENCY_FILE_NAMES, parse_dependency_file
from app.domain.resume.schemas import ProjectInfoDict, RepoContext, ResumeRequest, UserStats
from app.infra.github.client import (
    get_authenticated_user,
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
    "filter_tech_stack_by_position",
    "validate_position_match",
]

logger = get_logger(__name__)

GITHUB_API_SEMAPHORE_LIMIT = 5

MEANINGFUL_EXTENSIONS = frozenset(
    [
        "py",
        "js",
        "ts",
        "jsx",
        "tsx",
        "java",
        "kt",
        "go",
        "rs",
        "rb",
        "c",
        "cpp",
        "h",
        "hpp",
        "cs",
        "swift",
        "m",
        "scala",
        "php",
    ]
)

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


NOISE_COMMIT_PATTERNS = [
    r"^merge\s",
    r"^initial commit",
    r"^first commit",
    r"^update readme",
    r"^update \.gitignore",
    r"^fix typo",
    r"^typo",
    r"^wip$",
    r"^wip\s",
    r"^chore:\s*release",
    r"^bump version",
    r"^v\d+\.\d+",
]

_NOISE_REGEX = re.compile("|".join(NOISE_COMMIT_PATTERNS), re.IGNORECASE)


def _filter_noise_commits(commits: list) -> list:
    """의미없는 커밋 메시지 필터링"""
    filtered = []
    for commit in commits:
        first_line = commit.message.split("\n")[0].strip()
        if not _NOISE_REGEX.search(first_line):
            filtered.append(commit)
    return filtered


def _prioritize_pulls(pulls: list) -> list:
    """PR을 중요도 순으로 정렬"""

    def score(pr) -> int:
        title_lower = pr.title.lower()
        s = 0

        if re.search(r"feat|feature|add|implement", title_lower):
            s += 30
        elif re.search(r"fix|bug|resolve", title_lower):
            s += 20
        elif re.search(r"refactor|improve", title_lower):
            s += 15

        changes = pr.additions + pr.deletions
        if changes >= 500:
            s += 20
        elif changes >= 100:
            s += 10

        if re.search(r"typo|readme|bump", title_lower):
            s -= 20

        return s

    return sorted(pulls, key=score, reverse=True)


def _summarize_pr_body(body: str, max_length: int = 300) -> str:
    """PR 본문에서 유의미한 내용만 추출"""
    text = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    text = re.sub(r"- \[[ x]\] .+", "", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"#+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if not text:
        return ""

    text = text.replace("\n", " ")
    return text[:max_length]


def _format_commit_message(commit) -> str:
    """커밋 메시지를 유의미하게 포맷"""
    lines = commit.message.strip().split("\n")
    first_line = lines[0].strip()

    body_first_line = ""
    for line in lines[1:]:
        stripped = line.strip()
        if stripped:
            body_first_line = stripped
            break

    if body_first_line:
        return f"commit: {first_line} | {body_first_line}"
    return f"commit: {first_line}"


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


async def _collect_single_project(
    repo_url: str,
    token: str | None,
    username: str | None,
    author_name: str | None,
    semaphore: asyncio.Semaphore,
) -> ProjectInfoDict | None:
    """단일 레포지토리의 프로젝트 정보 수집

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰
        username: 인증된 사용자명
        author_name: 인증된 사용자 실명
        semaphore: GitHub API 동시 요청 제한 세마포어

    Returns:
        프로젝트 정보 딕셔너리, 수집 실패 또는 빈 레포이면 None
    """
    _, repo_name = parse_repo_url(repo_url)

    async with semaphore:
        try:
            project_info = await get_project_info(
                repo_url,
                token,
                author=username,
                author_name=author_name,
            )
            file_tree = project_info["file_tree"]
            commits = _filter_noise_commits(project_info["commits"])
            pulls = project_info["pulls"]

            if _is_empty_repository(file_tree):
                logger.info("빈 레포지토리 스킵", repo=repo_name)
                return None

            dependencies = await _parse_dependencies(repo_url, file_tree, token)
            messages = _format_messages(commits, pulls)

            logger.info(
                "프로젝트 정보 수집 완료",
                repo=repo_name,
                files=len(file_tree),
                deps=len(dependencies),
                messages=len(messages),
            )

            return {
                "repo_name": repo_name,
                "repo_url": repo_url,
                "file_tree": _summarize_file_tree(file_tree),
                "dependencies": dependencies,
                "messages": messages,
            }

        except httpx.HTTPStatusError as e:
            logger.error(
                "프로젝트 정보 수집 실패 - HTTP 오류",
                repo=repo_name,
                status=e.response.status_code,
            )
            return None

        except Exception as e:
            logger.error("프로젝트 정보 수집 실패", repo=repo_name, error=str(e), exc_info=True)
            return None


async def collect_project_info(request: ResumeRequest) -> list[ProjectInfoDict]:
    """파일 목록 + 의존성 파일 기반으로 프로젝트 정보 수집

    Args:
        request: 이력서 생성 요청

    Returns:
        유효한 프로젝트 정보 리스트
    """
    if github_mock_var.get():
        from app.infra.github.mock_data import MOCK_DELAY, make_mock_project_info

        await asyncio.sleep(MOCK_DELAY)
        return [make_mock_project_info(url, parse_repo_url(url)[1]) for url in request.repo_urls]

    unique_urls = list(dict.fromkeys(request.repo_urls))
    if len(unique_urls) < len(request.repo_urls):
        logger.warning("중복 URL 제거", original=len(request.repo_urls), unique=len(unique_urls))

    username = None
    author_name = None
    if request.github_token:
        username, author_name = await get_authenticated_user(request.github_token)
        if username:
            logger.info("인증된 사용자로 필터링", username=username, name=author_name)

    semaphore = asyncio.Semaphore(GITHUB_API_SEMAPHORE_LIMIT)
    tasks = [
        _collect_single_project(repo_url, request.github_token, username, author_name, semaphore)
        for repo_url in unique_urls
    ]
    gathered = await asyncio.gather(*tasks)
    results = [item for item in gathered if item is not None]

    if unique_urls and not results:
        logger.warning("모든 레포지토리에서 프로젝트 정보 수집 실패", total=len(unique_urls))

    logger.info("전체 프로젝트 정보 수집 완료", valid=len(results))
    return results


def _is_empty_repository(file_tree: list[str]) -> bool:
    """레포지토리가 의미있는 코드 파일을 포함하는지 검사

    Args:
        file_tree: 파일 경로 리스트

    Returns:
        True면 빈 레포지토리로 판단
    """
    for path in file_tree:
        if "." in path:
            ext = path.rsplit(".", 1)[-1].lower()
            if ext in MEANINGFUL_EXTENSIONS:
                return False
    return True


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
        if filename in DEPENDENCY_FILE_NAMES:
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
    """커밋과 PR 정보를 메시지 리스트로 포맷팅

    Args:
        commits: CommitInfo 리스트
        pulls: PRInfoExtended 리스트

    Returns:
        메시지 리스트
    """
    messages = []

    sorted_pulls = _prioritize_pulls(pulls)
    for pr in sorted_pulls:
        msg = f"PR #{pr.number}: {pr.title}"
        msg += f" [커밋 {pr.commits_count}개, +{pr.additions}/-{pr.deletions}]"
        if pr.body:
            body_summary = _summarize_pr_body(pr.body)
            if body_summary:
                msg += f" | {body_summary}"
        messages.append(msg)

    for commit in commits:
        messages.append(_format_commit_message(commit))

    return messages


async def _collect_single_context(
    repo_url: str,
    token: str | None,
    semaphore: asyncio.Semaphore,
) -> tuple[str, RepoContext]:
    """단일 레포지토리의 컨텍스트 정보 수집

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰
        semaphore: GitHub API 동시 요청 제한 세마포어

    Returns:
        레포 이름과 RepoContext 튜플
    """
    _, repo_name = parse_repo_url(repo_url)

    async with semaphore:
        try:
            context = await get_repo_context(repo_url, token)
            return repo_name, RepoContext(
                name=repo_name,
                languages=context["languages"],
                description=context["description"],
                topics=context["topics"],
                readme_summary=context["readme"],
            )
        except Exception as e:
            logger.warning("컨텍스트 수집 실패", repo=repo_name, error=str(e))
            return repo_name, RepoContext(
                name=repo_name,
                languages={},
                description=None,
                topics=[],
                readme_summary=None,
            )


async def collect_repo_contexts(request: ResumeRequest) -> dict[str, RepoContext]:
    """각 레포지토리의 컨텍스트 정보 수집.

    Args:
        request: 이력서 생성 요청

    Returns:
        레포 이름을 키로 하는 RepoContext 딕셔너리
    """
    if github_mock_var.get():
        from app.infra.github.mock_data import MOCK_DELAY, make_mock_repo_context

        await asyncio.sleep(MOCK_DELAY)
        return {
            parse_repo_url(url)[1]: make_mock_repo_context(parse_repo_url(url)[1])
            for url in request.repo_urls
        }

    unique_urls = list(dict.fromkeys(request.repo_urls))
    semaphore = asyncio.Semaphore(GITHUB_API_SEMAPHORE_LIMIT)
    tasks = [
        _collect_single_context(repo_url, request.github_token, semaphore)
        for repo_url in unique_urls
    ]
    results = await asyncio.gather(*tasks)
    contexts = dict(results)

    logger.info("컨텍스트 수집 완료", repos=len(contexts))
    return contexts


async def collect_user_stats(username: str, token: str | None) -> UserStats | None:
    """사용자 GitHub 통계 수집.

    Args:
        username: GitHub 유저네임
        token: GitHub OAuth 토큰

    Returns:
        사용자 통계 정보, 토큰 없거나 실패하면 None
    """
    if github_mock_var.get():
        from app.infra.github.mock_data import MOCK_DELAY, MOCK_USER_STATS

        await asyncio.sleep(MOCK_DELAY)
        return MOCK_USER_STATS

    if not token:
        logger.info("토큰 없음, 사용자 통계 수집 건너뜀", username=username)
        return None

    try:
        stats = await get_user_stats(username, token)
        logger.info(
            "사용자 통계 수집 완료",
            username=username,
            commits=stats.total_commits,
            prs=stats.total_prs,
            issues=stats.total_issues,
        )
        return stats
    except Exception as e:
        logger.warning("사용자 통계 수집 실패", username=username, error=str(e))
        return None


def _get_allowed_techs_for_position(position: str) -> frozenset[str] | None:
    """포지션에 허용된 기술 스택 반환

    Args:
        position: 지원 포지션

    Returns:
        허용된 기술 스택 frozenset, 매칭되지 않으면 None
    """
    position_lower = position.lower()
    for key, techs in POSITION_TECH_MAP.items():
        if key in position_lower:
            return techs
    return None


def validate_position_match(
    position: str,
    dependencies: list[str],
) -> tuple[bool, str]:
    """포지션과 기술 스택의 적합성 검증

    Args:
        position: 지원 포지션
        dependencies: 의존성 리스트

    Returns:
        is_valid: 적합 여부
        error_message: 에러 메시지, 적합하면 빈 문자열
    """
    deps_lower = {dep.lower() for dep in dependencies}
    position_lower = position.lower()

    for keywords, required_techs, display_name in POSITION_VALIDATION_RULES:
        if any(keyword in position_lower for keyword in keywords):
            has_required = any(tech in dep for dep in deps_lower for tech in required_techs)
            if not has_required:
                return False, f"{display_name} 포지션에 맞는 기술 스택이 없습니다"
            return True, ""

    return True, ""


def _is_tech_allowed(tech_lower: str, allowed_techs: frozenset[str]) -> bool:
    """기술명이 허용 목록에 포함되는지 단어 단위로 검사"""
    if tech_lower in allowed_techs:
        return True

    first_word = tech_lower.split()[0] if tech_lower else ""
    if first_word in allowed_techs:
        return True

    return False


def filter_tech_stack_by_position(
    tech_stack: list[str],
    position: str,
    max_count: int = 8,
    min_count: int = 5,
) -> list[str]:
    """포지션에 맞는 기술만 필터링하여 최대 max_count개 반환

    Args:
        tech_stack: 원본 기술 스택 리스트
        position: 지원 포지션
        max_count: 최대 반환 개수
        min_count: 최소 보장 개수

    Returns:
        필터링된 기술 스택 리스트
    """
    allowed_techs = _get_allowed_techs_for_position(position)
    if allowed_techs is None:
        allowed_techs = BACKEND_TECHS | FRONTEND_TECHS

    filtered = []
    non_excluded = []

    for tech in tech_stack:
        tech_lower = tech.lower()

        if tech_lower in EXCLUDED_TECHS:
            continue

        non_excluded.append(tech)

        if _is_tech_allowed(tech_lower, allowed_techs):
            filtered.append(tech)

    if len(filtered) < min_count:
        for tech in non_excluded:
            if tech not in filtered:
                filtered.append(tech)
            if len(filtered) >= min_count:
                break

    return filtered[:max_count]
