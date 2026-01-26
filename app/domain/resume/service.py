from app.core.logging import get_logger
from app.domain.resume.schemas import DiffAnalysisOutput, PRInfo, RepoContext, ResumeRequest
from app.infra.github.client import (
    get_commit_detail,
    get_commits,
    get_pull_files,
    get_pulls,
    get_repo_info,
    get_repo_languages,
    get_repo_readme,
    parse_repo_url,
)
from app.infra.llm.client import analyze_diffs_batch

logger = get_logger(__name__)

MIN_ADDED_LINES = 3

SKIP_FILENAMES = {
    # lock 파일
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "composer.lock",
    "Gemfile.lock",
    "go.sum",
    # 설정 파일
    ".gitignore",
    ".dockerignore",
    ".eslintrc.js",
    ".eslintrc.json",
    ".prettierrc",
    ".prettierrc.json",
    "tsconfig.json",
    "tsconfig.node.json",
    "vite.config.ts",
    "vite.config.js",
    "postcss.config.js",
    "tailwind.config.js",
    "tailwind.config.ts",
    "next.config.js",
    "next.config.ts",
    "webpack.config.js",
    "babel.config.js",
    ".babelrc",
    "jest.config.js",
    "jest.config.ts",
}

SKIP_EXTENSIONS = {".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}

SKIP_DIRECTORIES = {".vscode/", ".idea/", ".github/", ".husky/"}

MAX_PATCH_LENGTH = 2000


def _should_skip_file(filename: str) -> bool:
    """분석 가치가 없는 파일인지 판단."""
    if filename in SKIP_FILENAMES:
        return True
    if any(filename.startswith(d) for d in SKIP_DIRECTORIES):
        return True
    if filename.endswith(".iml"):
        return True
    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    if ext in SKIP_EXTENSIONS:
        return True
    return False


def _count_added_lines(patch: str) -> int:
    """patch에서 추가된 줄 수를 계산."""
    return sum(
        1 for line in patch.split("\n") if line.startswith("+") and not line.startswith("+++")
    )


async def collect_diffs(request: ResumeRequest) -> list[dict]:
    """GitHub에서 커밋을 조회하고 의미 있는 diff만 추출.

    Args:
        request: 이력서 생성 요청

    Returns:
        [{"repo_name": str, "diff_content": str}] 형태의 리스트
    """
    diffs = []
    skipped = 0

    for repo_url in request.repo_urls:
        _, repo_name = parse_repo_url(repo_url)
        commits = await get_commits(repo_url, request.github_token, per_page=30)

        for commit in commits:
            commit_detail = await get_commit_detail(repo_url, commit.sha, request.github_token)

            meaningful_patches = []
            for f in commit_detail.files:
                filename = f.get("filename", "")
                patch = f.get("patch", "")

                if not patch:
                    continue
                if _should_skip_file(filename):
                    continue
                if _count_added_lines(patch) < MIN_ADDED_LINES:
                    continue

                meaningful_patches.append(f"파일: {filename}\n{patch}")

            if meaningful_patches:
                diff_content = "\n".join(meaningful_patches)
                diffs.append({"repo_name": repo_name, "diff_content": diff_content})
            else:
                skipped += 1

    logger.info("diff 수집 완료 total=%d skipped=%d", len(diffs), skipped)
    return diffs


MAX_DIFFS_PER_BATCH = 10


async def analyze_experiences(diffs: list[dict]) -> list[DiffAnalysisOutput]:
    """수집된 diff들을 레포별로 순차 분석.

    Args:
        diffs: collect_diffs의 반환값

    Returns:
        분석된 경험 목록
    """
    repo_groups: dict[str, list[str]] = {}
    for diff in diffs:
        repo_name = diff["repo_name"]
        if repo_name not in repo_groups:
            repo_groups[repo_name] = []
        repo_groups[repo_name].append(diff["diff_content"])

    all_experiences = []
    batch_count = 0

    for repo_name, diff_contents in repo_groups.items():
        for i in range(0, len(diff_contents), MAX_DIFFS_PER_BATCH):
            batch = diff_contents[i : i + MAX_DIFFS_PER_BATCH]
            batch_result = await analyze_diffs_batch(batch, repo_name)
            all_experiences.extend(batch_result)
            batch_count += 1

    logger.info("경험 분석 완료 batches=%d experiences=%d", batch_count, len(all_experiences))
    return all_experiences


def format_pr_data(prs: list[PRInfo]) -> list[dict]:
    """PR 목록을 LLM 입력 형식으로 변환 (제목/본문만).

    Args:
        prs: PR 정보 목록

    Returns:
        [{"repo_name": str, "diff_content": str}] 형태의 리스트
    """
    results = []
    for pr in prs:
        _, repo_name = parse_repo_url(pr.repo_url)
        content = f"PR #{pr.number}: {pr.title}"
        if pr.body:
            content += f"\n\n{pr.body}"
        results.append({"repo_name": repo_name, "diff_content": content})
    return results


async def collect_pr_diffs_for_repo(
    repo_url: str, token: str | None = None, per_page: int = 30
) -> list[dict]:
    """레포지토리에서 PR의 실제 코드 변경을 수집.

    Args:
        repo_url: GitHub 레포지토리 URL
        token: GitHub OAuth 토큰
        per_page: 가져올 PR 개수

    Returns:
        [{"repo_name": str, "diff_content": str}] 형태의 리스트
    """
    _, repo_name = parse_repo_url(repo_url)
    results = []

    prs = await get_pulls(repo_url, token, per_page=per_page)
    if not prs:
        return results

    for pr in prs:
        try:
            files = await get_pull_files(repo_url, pr.number, token)

            meaningful_patches = []
            for f in files:
                filename = f.get("filename", "")
                patch = f.get("patch", "")

                if not patch:
                    continue
                if _should_skip_file(filename):
                    continue
                if _count_added_lines(patch) < MIN_ADDED_LINES:
                    continue

                truncated = patch[:MAX_PATCH_LENGTH] if len(patch) > MAX_PATCH_LENGTH else patch
                meaningful_patches.append(f"파일: {filename}\n{truncated}")

            if meaningful_patches:
                content = f"PR #{pr.number}: {pr.title}\n\n"
                content += "\n".join(meaningful_patches)
                results.append({"repo_name": repo_name, "diff_content": content})

        except Exception as e:
            logger.warning("PR 파일 수집 실패 pr=%d error=%s", pr.number, e)

    logger.info("PR diff 수집 완료 repo=%s count=%d", repo_name, len(results))
    return results


async def collect_data(request: ResumeRequest) -> list[dict]:
    """PR 기반 데이터 수집 (PR 없으면 commit 폴백).

    Args:
        request: 이력서 생성 요청

    Returns:
        [{"repo_name": str, "diff_content": str}] 형태의 리스트
    """
    results = []

    for repo_url in request.repo_urls:
        _, repo_name = parse_repo_url(repo_url)

        try:
            prs = await get_pulls(repo_url, request.github_token)

            if prs:
                pr_data = format_pr_data(prs)
                results.extend(pr_data)
                logger.info("PR 데이터 수집 repo=%s count=%d", repo_name, len(prs))
            else:
                logger.info("PR 없음, commit 폴백 repo=%s", repo_name)
                commit_data = await _collect_diffs_for_repo(repo_url, request)
                results.extend(commit_data)

        except Exception as e:
            logger.warning("PR 수집 실패, commit 폴백 repo=%s error=%s", repo_name, e)
            commit_data = await _collect_diffs_for_repo(repo_url, request)
            results.extend(commit_data)

    logger.info("데이터 수집 완료 total=%d", len(results))
    return results


async def _collect_diffs_for_repo(repo_url: str, request: ResumeRequest) -> list[dict]:
    """단일 레포에서 commit diff 수집.

    Args:
        repo_url: GitHub 레포지토리 URL
        request: 이력서 생성 요청

    Returns:
        [{"repo_name": str, "diff_content": str}] 형태의 리스트
    """
    _, repo_name = parse_repo_url(repo_url)
    diffs = []
    skipped = 0

    commits = await get_commits(repo_url, request.github_token, per_page=30)

    for commit in commits:
        commit_detail = await get_commit_detail(repo_url, commit.sha, request.github_token)

        meaningful_patches = []
        for f in commit_detail.files:
            filename = f.get("filename", "")
            patch = f.get("patch", "")

            if not patch:
                continue
            if _should_skip_file(filename):
                continue
            if _count_added_lines(patch) < MIN_ADDED_LINES:
                continue

            truncated = patch[:MAX_PATCH_LENGTH] if len(patch) > MAX_PATCH_LENGTH else patch
            logger.info("파일 포함 file=%s orig=%d trunc=%d", filename, len(patch), len(truncated))
            meaningful_patches.append(f"파일: {filename}\n{truncated}")

        if meaningful_patches:
            diff_content = "\n".join(meaningful_patches)
            diffs.append({"repo_name": repo_name, "diff_content": diff_content})
        else:
            skipped += 1

    logger.info("commit diff 수집 repo=%s total=%d skipped=%d", repo_name, len(diffs), skipped)
    return diffs


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
            languages = await get_repo_languages(repo_url, request.github_token)
            info = await get_repo_info(repo_url, request.github_token)
            readme = await get_repo_readme(repo_url, request.github_token)

            contexts[repo_name] = RepoContext(
                name=repo_name,
                languages=languages,
                description=info["description"],
                topics=info["topics"],
                readme_summary=readme,
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
