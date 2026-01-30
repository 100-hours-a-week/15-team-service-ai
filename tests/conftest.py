"""테스트 공통 fixture"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.resume.schemas import (
    EvaluationOutput,
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
