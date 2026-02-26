from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import ErrorCode
from app.domain.resume.schemas import (
    ProjectInfo,
    RepoContext,
    ResumeData,
    ResumeRequest,
    ResumeState,
    UserStats,
)
from app.domain.resume.workflow import (
    collect_data_node,
    finalize_node,
    generate_node,
    should_continue,
)


class TestCollectDataNode:
    """collect_data_node 함수 테스트"""

    @pytest.fixture
    def base_state(self) -> ResumeState:
        """기본 상태"""
        return ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/testuser/testrepo"],
                position="백엔드 개발자",
                github_token="test-token",
            ),
            job_id="test-job-123",
        )

    async def test_collect_data_success(self, base_state):
        """정상 데이터 수집"""
        mock_project_info = [
            {
                "repo_name": "testrepo",
                "repo_url": "https://github.com/testuser/testrepo",
                "dependencies": ["fastapi"],
                "messages": ["feat: init"],
            }
        ]
        mock_repo_contexts = {
            "testrepo": RepoContext(
                name="testrepo",
                languages={"Python": 10000},
                description="Test repo",
                topics=["python"],
                readme_summary="Test readme",
            )
        }
        mock_user_stats = UserStats(total_commits=100, total_prs=10, total_issues=5)

        with (
            patch(
                "app.domain.resume.workflow.collect_project_info",
                new_callable=AsyncMock,
                return_value=mock_project_info,
            ),
            patch(
                "app.domain.resume.workflow.collect_repo_contexts",
                new_callable=AsyncMock,
                return_value=mock_repo_contexts,
            ),
            patch(
                "app.domain.resume.workflow.collect_user_stats",
                new_callable=AsyncMock,
                return_value=mock_user_stats,
            ),
        ):
            result = await collect_data_node(base_state)

        assert result["project_info"] == mock_project_info
        assert result["repo_contexts"] == mock_repo_contexts
        assert result["user_stats"] == mock_user_stats
        assert result.get("error_code") is None

    async def test_collect_data_empty_project_info(self, base_state):
        """프로젝트 정보가 비어있을 때 에러 상태 설정"""
        with (
            patch(
                "app.domain.resume.workflow.collect_project_info",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.collect_repo_contexts",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await collect_data_node(base_state)

        assert result["error_code"] == ErrorCode.COLLECT_DATA_FAILED
        assert "프로젝트 정보 수집 실패" in result["error_message"]

    async def test_collect_data_github_api_error(self, base_state):
        """GitHub API 오류 시 에러 상태 설정"""
        mock_response = httpx.Response(401, request=httpx.Request("GET", "test"))
        http_error = httpx.HTTPStatusError(
            "Unauthorized", request=mock_response.request, response=mock_response
        )

        with patch(
            "app.domain.resume.workflow.collect_project_info",
            new_callable=AsyncMock,
            side_effect=http_error,
        ):
            result = await collect_data_node(base_state)

        assert result["error_code"] == ErrorCode.GITHUB_UNAUTHORIZED
        assert "인증 실패" in result["error_message"]

    async def test_collect_data_invalid_url(self, base_state):
        """잘못된 URL 시 에러 상태 설정"""
        with patch(
            "app.domain.resume.workflow.collect_project_info",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid URL format"),
        ):
            result = await collect_data_node(base_state)

        assert result["error_code"] == ErrorCode.INVALID_INPUT
        assert "잘못된 입력값" in result["error_message"]


class TestGenerateNode:
    """generate_node 함수 테스트"""

    @pytest.fixture
    def base_state(self) -> ResumeState:
        """기본 상태"""
        return ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/testuser/testrepo"],
                position="백엔드 개발자",
                github_token="test-token",
            ),
            job_id="test-job-123",
            project_info=[
                {
                    "repo_name": "testrepo",
                    "repo_url": "https://github.com/testuser/testrepo",
                    "dependencies": ["fastapi"],
                    "messages": ["feat: init"],
                }
            ],
            repo_contexts={},
        )

    async def test_generate_success(self, base_state):
        """정상 이력서 생성"""
        mock_resume = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test Project",
                    repo_url="https://github.com/testuser/testrepo",
                    description="테스트 프로젝트",
                    tech_stack=["Python", "FastAPI"],
                )
            ]
        )

        with patch(
            "app.domain.resume.workflow.generate_resume",
            new_callable=AsyncMock,
            return_value=mock_resume,
        ):
            result = await generate_node(base_state)

        assert result["resume_data"] == mock_resume
        assert result.get("error_code") is None

    async def test_generate_no_project_info(self, base_state):
        """project_info가 없을 때 에러 상태 설정"""
        state_without_project = dict(base_state)
        state_without_project["project_info"] = None

        result = await generate_node(state_without_project)

        assert result["error_code"] == ErrorCode.GENERATE_ERROR
        assert "프로젝트 정보가 없습니다" in result["error_message"]

    async def test_generate_llm_api_error(self, base_state):
        """LLM API 오류 시 에러 상태 설정"""
        mock_response = httpx.Response(500, request=httpx.Request("POST", "test"))
        http_error = httpx.HTTPStatusError(
            "Server Error", request=mock_response.request, response=mock_response
        )

        with patch(
            "app.domain.resume.workflow.generate_resume",
            new_callable=AsyncMock,
            side_effect=http_error,
        ):
            result = await generate_node(base_state)

        assert result["error_code"] == ErrorCode.LLM_API_ERROR
        assert "HTTP 500" in result["error_message"]

    async def test_generate_validation_error(self, base_state):
        """생성 검증 오류 시 에러 상태 설정"""
        with patch(
            "app.domain.resume.workflow.generate_resume",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid format"),
        ):
            result = await generate_node(base_state)

        assert result["error_code"] == ErrorCode.GENERATE_VALIDATION_ERROR
        assert "검증 오류" in result["error_message"]


class TestFinalizeNode:
    """finalize_node 함수 테스트"""

    @pytest.fixture
    def base_state(self) -> ResumeState:
        """기본 상태"""
        return ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/testuser/testrepo"],
                position="백엔드 개발자",
                github_token="test-token",
            ),
            job_id="test-job-123",
            project_info=[
                {
                    "repo_name": "testrepo",
                    "repo_url": "https://github.com/testuser/testrepo",
                    "dependencies": ["fastapi"],
                    "messages": ["feat: init"],
                }
            ],
            resume_data=ResumeData(
                projects=[
                    ProjectInfo(
                        name="Test",
                        repo_url="https://github.com/testuser/testrepo",
                        description="- 테스트 기능 구현",
                        tech_stack=["Python", "FastAPI", "PostgreSQL"],
                    )
                ]
            ),
        )

    async def test_finalize_success(self, base_state):
        """정상 윤문 - 정제된 ResumeData 반환"""
        polished_resume = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/testuser/testrepo",
                    description="- FastAPI 기반 테스트 기능 설계 및 구현",
                    tech_stack=["Python", "FastAPI", "PostgreSQL"],
                )
            ]
        )

        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.finalize_resume",
                new_callable=AsyncMock,
                return_value=polished_resume,
            ),
        ):
            result = await finalize_node(base_state)

        assert result["resume_data"] == polished_resume

    async def test_finalize_llm_error_graceful(self, base_state):
        """LLM 실패 시 원본 ResumeData 유지"""
        original_resume = base_state["resume_data"]

        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.finalize_resume",
                new_callable=AsyncMock,
                side_effect=Exception("LLM 호출 실패"),
            ),
        ):
            result = await finalize_node(base_state)

        assert result["resume_data"] == original_resume

    async def test_finalize_with_format_violations(self, base_state):
        """포맷 위반이 있어도 Finalizer가 수정하여 반환"""
        mock_violations = [
            {
                "project": "Test",
                "rule": "forbidden_ending",
                "detail": "금지 어미 '~했습니다' 사용",
            }
        ]
        polished_resume = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/testuser/testrepo",
                    description="- FastAPI 기반 테스트 기능 구현",
                    tech_stack=["Python", "FastAPI", "PostgreSQL"],
                )
            ]
        )

        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=mock_violations,
            ),
            patch(
                "app.domain.resume.workflow.finalize_resume",
                new_callable=AsyncMock,
                return_value=polished_resume,
            ) as mock_finalize,
        ):
            result = await finalize_node(base_state)

        assert result["resume_data"] == polished_resume
        call_kwargs = mock_finalize.call_args[1]
        assert "금지 어미" in call_kwargs["violations"]

    async def test_finalize_hallucinated_repo_url_keeps_original(self, base_state):
        """Finalizer가 repo_url을 바꾸면 원본 유지"""
        original_resume = base_state["resume_data"]
        hallucinated = ResumeData(
            projects=[
                ProjectInfo(
                    name="Sample Project",
                    repo_url="https://github.com/sample/repo",
                    description="- RESTful API 기반의 백엔드 서버 설계",
                    tech_stack=["Java", "Spring Boot"],
                )
            ]
        )

        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.finalize_resume",
                new_callable=AsyncMock,
                return_value=hallucinated,
            ),
        ):
            result = await finalize_node(base_state)

        assert result["resume_data"] == original_resume

    async def test_finalize_wrong_project_count_keeps_original(self, base_state):
        """Finalizer가 프로젝트 수를 바꾸면 원본 유지"""
        original_resume = base_state["resume_data"]
        wrong_count = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/testuser/testrepo",
                    description="- 기능 구현",
                    tech_stack=["Python"],
                ),
                ProjectInfo(
                    name="Extra",
                    repo_url="https://github.com/extra/repo",
                    description="- 추가 프로젝트",
                    tech_stack=["Java"],
                ),
            ]
        )

        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.finalize_resume",
                new_callable=AsyncMock,
                return_value=wrong_count,
            ),
        ):
            result = await finalize_node(base_state)

        assert result["resume_data"] == original_resume


class TestShouldContinue:
    """should_continue 조건 함수 테스트"""

    def test_returns_end_when_error(self):
        """에러 있을 때 end 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
            error_code=ErrorCode.GITHUB_API_ERROR,
            error_message="API Error",
        )

        result = should_continue(state)

        assert result == "end"

    def test_returns_plan_when_no_error(self):
        """에러 없을 때 plan 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
        )

        result = should_continue(state)

        assert result == "plan"
