import asyncio

from app.core.logging import get_logger
from app.domain.resume.schemas import DiffAnalysisOutput, PRInfo, ResumeRequest
from app.infra.github.client import get_commit_detail, get_commits, get_pulls, parse_repo_url
from app.infra.llm.client import analyze_diffs_batch

logger = get_logger(__name__)

MAX_CONCURRENT_LLM = 5
MIN_ADDED_LINES = 3

SKIP_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "composer.lock",
    "Gemfile.lock",
    "go.sum",
}

SKIP_EXTENSIONS = {".md", ".txt", ".rst"}

SKIP_DIRECTORIES = {".vscode/", ".idea/"}


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
        1
        for line in patch.split("\n")
        if line.startswith("+") and not line.startswith("+++")
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
            commit_detail = await get_commit_detail(
                repo_url, commit.sha, request.github_token
            )

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
    """수집된 diff들을 레포별로 묶어 배치 분석.

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

    batches = []
    for repo_name, diff_contents in repo_groups.items():
        for i in range(0, len(diff_contents), MAX_DIFFS_PER_BATCH):
            batch = diff_contents[i : i + MAX_DIFFS_PER_BATCH]
            batches.append((repo_name, batch))

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

    async def _analyze_batch(
        repo_name: str, batch: list[str]
    ) -> list[DiffAnalysisOutput]:
        async with semaphore:
            return await analyze_diffs_batch(batch, repo_name)

    results = await asyncio.gather(
        *[_analyze_batch(repo_name, batch) for repo_name, batch in batches]
    )

    all_experiences = []
    for batch_result in results:
        all_experiences.extend(batch_result)

    logger.info(
        "경험 분석 완료 batches=%d experiences=%d", len(batches), len(all_experiences)
    )
    return all_experiences


def format_pr_data(prs: list[PRInfo]) -> list[dict]:
    """PR 목록을 LLM 입력 형식으로 변환.

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

            meaningful_patches.append(f"파일: {filename}\n{patch}")

        if meaningful_patches:
            diff_content = "\n".join(meaningful_patches)
            diffs.append({"repo_name": repo_name, "diff_content": diff_content})
        else:
            skipped += 1

    logger.info("commit diff 수집 repo=%s total=%d skipped=%d", repo_name, len(diffs), skipped)
    return diffs
