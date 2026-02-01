"""테스트 공통 fixture"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.resume.schemas import (
    CommitInfo,
    EvaluationOutput,
    PRInfoExtended,
    ProjectInfo,
    RepoContext,
    ResumeData,
    ResumeRequest,
    ResumeState,
    UserStats,
)
from app.main import app


@pytest.fixture
def sample_resume_request() -> ResumeRequest:
    """테스트용 이력서 요청"""
    return ResumeRequest(
        repo_urls=["https://github.com/testuser/testrepo"],
        position="백엔드 개발자",
        company="테스트회사",
        github_token="test-token-123",
        callback_url="http://localhost:8080/callback",
    )


@pytest.fixture
def sample_project_info() -> list[dict]:
    """테스트용 프로젝트 정보"""
    return [
        {
            "repo_name": "testrepo",
            "repo_url": "https://github.com/testuser/testrepo",
            "file_tree": ["src/main.py", "requirements.txt", "README.md"],
            "dependencies": ["fastapi", "uvicorn", "pydantic"],
            "messages": ["feat: 초기 설정", "fix: 버그 수정"],
        }
    ]


@pytest.fixture
def sample_repo_contexts() -> dict[str, RepoContext]:
    """테스트용 레포지토리 컨텍스트"""
    return {
        "testrepo": RepoContext(
            name="testrepo",
            languages={"Python": 10000, "JavaScript": 2000},
            description="테스트 프로젝트입니다",
            topics=["python", "fastapi", "backend"],
            readme_summary="이 프로젝트는 FastAPI를 사용한 백엔드 서비스입니다",
        )
    }


@pytest.fixture
def sample_user_stats() -> UserStats:
    """테스트용 사용자 통계"""
    return UserStats(
        total_commits=150,
        total_prs=30,
        total_issues=10,
    )


@pytest.fixture
def sample_resume_data() -> ResumeData:
    """테스트용 이력서 데이터"""
    return ResumeData(
        projects=[
            ProjectInfo(
                name="테스트 프로젝트",
                repo_url="https://github.com/testuser/testrepo",
                description="FastAPI를 활용한 백엔드 서비스 개발",
                tech_stack=["Python", "FastAPI", "PostgreSQL"],
            )
        ]
    )


@pytest.fixture
def sample_evaluation_pass() -> EvaluationOutput:
    """테스트용 평가 결과 - 통과"""
    return EvaluationOutput(
        result="pass",
        violated_rule=None,
        violated_item=None,
        feedback="이력서가 모든 기준을 충족합니다",
    )


@pytest.fixture
def sample_evaluation_fail() -> EvaluationOutput:
    """테스트용 평가 결과 - 실패"""
    return EvaluationOutput(
        result="fail",
        violated_rule=2,
        violated_item="tech_stack",
        feedback="기술 스택이 너무 적습니다. 최소 3개 이상의 기술을 포함해주세요",
    )


@pytest.fixture
def sample_resume_state(
    sample_resume_request, sample_project_info, sample_resume_data
) -> ResumeState:
    """테스트용 워크플로우 상태"""
    return ResumeState(
        request=sample_resume_request,
        job_id="test-job-123",
        session_id="test-session-123",
        project_info=sample_project_info,
        repo_contexts={},
        user_stats=None,
        resume_data=sample_resume_data,
        evaluation="",
        evaluation_feedback="",
        retry_count=0,
        error_code="",
        error_message="",
    )


@pytest.fixture
def async_client():
    """비동기 HTTP 클라이언트"""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def mock_vllm_client():
    """이력서 생성용 LLM 클라이언트 mock"""
    with patch("app.infra.llm.client.get_generator_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_gemini_client():
    """이력서 평가용 LLM 클라이언트 mock"""
    with patch("app.infra.llm.client.get_evaluator_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_github_response():
    """GitHub API 응답 mock 생성"""
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    return mock


@pytest.fixture
def create_http_error():
    """HTTPStatusError 생성 helper"""

    def _create(status_code: int, message: str = "Error"):
        return httpx.HTTPStatusError(
            message,
            request=httpx.Request("GET", "https://test.com"),
            response=httpx.Response(status_code),
        )

    return _create


@pytest.fixture
def mock_workflow():
    """LangGraph 워크플로우 mock"""
    workflow = MagicMock()
    workflow.ainvoke = AsyncMock()
    return workflow


@pytest.fixture
def sample_pr() -> PRInfoExtended:
    """테스트용 PR 데이터"""
    return PRInfoExtended(
        number=1,
        title="Add feature",
        body="This PR adds a new feature",
        author="user1",
        merged_at="2024-01-01",
        repo_url="https://github.com/user/repo",
        commits_count=3,
        additions=100,
        deletions=20,
    )


@pytest.fixture
def sample_commits() -> list[CommitInfo]:
    """테스트용 커밋 리스트"""
    return [
        CommitInfo(sha="abc123", message="Fix bug\n\nDetailed description", author="user1"),
        CommitInfo(sha="def456", message="Add test", author="user2"),
    ]


@pytest.fixture
def mock_callback_settings():
    """콜백 설정 mock"""
    with patch("app.api.v1.resume.settings") as mock:
        mock.callback_max_retries = 3
        mock.callback_retry_base_delay = 0.01
        mock.ai_callback_secret = "secret"
        yield mock
