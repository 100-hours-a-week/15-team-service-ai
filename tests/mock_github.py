import asyncio

from app.domain.resume.schemas import CommitInfo, PRInfoExtended, UserStats

MOCK_DELAY = 2.0

MOCK_REPO_URL = "https://github.com/testuser/testrepo"

# ── PR 담당 ──────────────────────────────────────────────────────────────────

MOCK_PRS = [
    PRInfoExtended(
        number=1,
        title="feat: 사용자 인증 기능 추가",
        body="JWT 기반 인증 시스템을 구현했습니다.\n\n- 로그인/로그아웃 API\n- 토큰 갱신 로직",
        author="testuser",
        merged_at="2024-01-15T10:00:00Z",
        repo_url=MOCK_REPO_URL,
        commits_count=4,
        additions=230,
        deletions=15,
    ),
    PRInfoExtended(
        number=2,
        title="feat: 레포지토리 분석 워크플로우 구현",
        body="LangGraph를 이용한 레포 분석 파이프라인 추가",
        author="testuser",
        merged_at="2024-02-01T09:00:00Z",
        repo_url=MOCK_REPO_URL,
        commits_count=7,
        additions=580,
        deletions=40,
    ),
]

# ── Commit 담당 ───────────────────────────────────────────────────────────────

MOCK_COMMITS = [
    CommitInfo(sha="a1b2c3d", message="feat: 초기 프로젝트 설정", author="testuser"),
    CommitInfo(sha="e4f5g6h", message="feat: FastAPI 라우터 구성", author="testuser"),
    CommitInfo(sha="i7j8k9l", message="fix: 인증 미들웨어 버그 수정", author="testuser"),
    CommitInfo(sha="m1n2o3p", message="refactor: 서비스 레이어 분리", author="testuser"),
    CommitInfo(sha="q4r5s6t", message="feat: 이력서 생성 워크플로우 추가", author="testuser"),
]

# ── GitHub Context 담당 ───────────────────────────────────────────────────────

MOCK_CONTEXT = {
    "languages": {"Python": 85000, "Dockerfile": 2000, "Shell": 500},
    "description": "GitHub 레포지토리 데이터를 분석해 이력서를 생성하는 FastAPI 백엔드 서비스",
    "topics": ["fastapi", "langgraph", "python", "llm", "resume"],
    "readme": "# Dev Experience Extractor\n\nGitHub 레포지토리를 분석하여 이력서를 자동 생성합니다.",  # noqa: E501
}

# ── 파일트리 담당 ──────────────────────────────────────────────────────────────

MOCK_FILE_TREE = [
    "app/main.py",
    "app/core/config.py",
    "app/api/v2/resume.py",
    "app/domain/resume/service.py",
    "app/infra/github/client.py",
    "pyproject.toml",
    "Dockerfile",
    "README.md",
    "tests/conftest.py",
]

# ── 의존성 파일 담당 ──────────────────────────────────────────────────────────

MOCK_DEPENDENCY_FILES: dict[str, str | None] = {
    "pyproject.toml": (
        "[project]\n"
        'name = "final-project"\n'
        'requires-python = ">=3.12"\n'
        "dependencies = [\n"
        '    "fastapi>=0.115.0",\n'
        '    "langgraph>=1.0.6",\n'
        '    "langchain-openai>=0.3.0",\n'
        '    "httpx>=0.28.1",\n'
        '    "structlog>=24.1.0",\n'
        "]\n"
    ),
    "package.json": None,
}


async def mock_get_project_info(repo_url: str, **kwargs) -> dict:
    """get_project_info mock: 파일트리 + 커밋 + PR 반환"""
    await asyncio.sleep(MOCK_DELAY)
    return {
        "file_tree": MOCK_FILE_TREE,
        "commits": MOCK_COMMITS,
        "pulls": MOCK_PRS,
    }


async def mock_get_repo_context(repo_url: str, **kwargs) -> dict:
    """get_repo_context mock: 언어/설명/토픽/README 반환"""
    await asyncio.sleep(MOCK_DELAY)
    return MOCK_CONTEXT


async def mock_get_files_content(  # noqa: E501
    repo_url: str, paths: list[str], **kwargs
) -> dict[str, str | None]:
    """get_files_content mock: 의존성 파일 내용 반환"""
    await asyncio.sleep(MOCK_DELAY)
    return {path: MOCK_DEPENDENCY_FILES.get(path) for path in paths}


async def mock_get_user_stats(username: str, token: str) -> UserStats:
    """get_user_stats mock: 사용자 GitHub 통계 반환"""
    await asyncio.sleep(MOCK_DELAY)
    return UserStats(total_commits=120, total_prs=18, total_issues=7)


async def mock_get_authenticated_user(token: str) -> tuple[str | None, str | None]:
    """get_authenticated_user mock: 인증된 사용자 정보 반환"""
    await asyncio.sleep(MOCK_DELAY)
    return "testuser", "Test User"
