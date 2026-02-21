from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import ErrorCode
from app.domain.resume.schemas import (
    EvaluationOutput,
    ProjectInfo,
    RepoContext,
    ResumeData,
    ResumeRequest,
    ResumeState,
    UserStats,
)
from app.domain.resume.workflow import (
    collect_data_node,
    evaluate_node,
    generate_node,
    should_continue,
)
from app.domain.resume.workflow_utils import (
    make_should_retry,
    should_evaluate,
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
        assert result["retry_count"] == 0
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
            retry_count=0,
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
            "app.domain.resume.workflow._generate_in_batches",
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

    async def test_generate_retry_increments_count(self, base_state):
        """재시도 시 retry_count 증가"""
        state_with_fail = dict(base_state)
        state_with_fail["evaluation"] = "fail"
        state_with_fail["retry_count"] = 1

        mock_resume = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/testuser/testrepo",
                    description="Test",
                    tech_stack=["Python"],
                )
            ]
        )

        with patch(
            "app.domain.resume.workflow._generate_in_batches",
            new_callable=AsyncMock,
            return_value=mock_resume,
        ):
            result = await generate_node(state_with_fail)

        assert result["retry_count"] == 2

    async def test_generate_llm_api_error(self, base_state):
        """LLM API 오류 시 에러 상태 설정"""
        mock_response = httpx.Response(500, request=httpx.Request("POST", "test"))
        http_error = httpx.HTTPStatusError(
            "Server Error", request=mock_response.request, response=mock_response
        )

        with patch(
            "app.domain.resume.workflow._generate_in_batches",
            new_callable=AsyncMock,
            side_effect=http_error,
        ):
            result = await generate_node(base_state)

        assert result["error_code"] == ErrorCode.LLM_API_ERROR
        assert "HTTP 500" in result["error_message"]

    async def test_generate_validation_error(self, base_state):
        """생성 검증 오류 시 에러 상태 설정"""
        with patch(
            "app.domain.resume.workflow._generate_in_batches",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid format"),
        ):
            result = await generate_node(base_state)

        assert result["error_code"] == ErrorCode.GENERATE_VALIDATION_ERROR
        assert "검증 오류" in result["error_message"]


class TestEvaluateNode:
    """evaluate_node 함수 테스트"""

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
            resume_data=ResumeData(
                projects=[
                    ProjectInfo(
                        name="Test",
                        repo_url="https://github.com/testuser/testrepo",
                        description="Test",
                        tech_stack=["Python"],
                    )
                ]
            ),
        )

    async def test_evaluate_pass(self, base_state):
        """평가 통과 결과 처리"""
        mock_evaluation = EvaluationOutput(
            result="pass",
            violated_rule=None,
            violated_item=None,
            feedback="이력서가 모든 기준을 충족합니다",
        )

        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.evaluate_resume",
                new_callable=AsyncMock,
                return_value=mock_evaluation,
            ),
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == "이력서가 모든 기준을 충족합니다"

    async def test_evaluate_fail(self, base_state):
        """평가 실패 결과 처리"""
        mock_evaluation = EvaluationOutput(
            result="fail",
            violated_rule=2,
            violated_item="tech_stack",
            feedback="기술 스택이 부족합니다",
        )

        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.evaluate_resume",
                new_callable=AsyncMock,
                return_value=mock_evaluation,
            ),
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "fail"
        assert result["evaluation_feedback"] == "기술 스택이 부족합니다"

    async def test_evaluate_llm_error_returns_pass(self, base_state):
        """LLM 오류 시 관용적으로 pass 처리"""
        mock_response = httpx.Response(500, request=httpx.Request("POST", "test"))
        http_error = httpx.HTTPStatusError(
            "Server Error", request=mock_response.request, response=mock_response
        )

        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.evaluate_resume",
                new_callable=AsyncMock,
                side_effect=http_error,
            ),
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == ""

    async def test_evaluate_value_error_returns_pass(self, base_state):
        """ValueError 시 관용적으로 pass 처리"""
        with (
            patch(
                "app.domain.resume.validators.validate_resume_format",
                return_value=[],
            ),
            patch(
                "app.domain.resume.workflow.evaluate_resume",
                new_callable=AsyncMock,
                side_effect=ValueError("Parse error"),
            ),
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == ""

    async def test_evaluate_format_violation_returns_fail(self, base_state):
        """코드 검증 위반 시 fail 처리"""
        mock_violations = [
            {
                "project": "Test",
                "rule": "기술 스택 최소 개수",
                "detail": "기술 스택이 3개 미만",
            }
        ]

        with patch(
            "app.domain.resume.validators.validate_resume_format",
            return_value=mock_violations,
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "fail"
        assert "기술 스택이 3개 미만" in result["evaluation_feedback"]


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

    def test_returns_generate_when_no_error(self):
        """에러 없을 때 generate 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
        )

        result = should_continue(state)

        assert result == "generate"


class TestShouldEvaluate:
    """should_evaluate 조건 함수 테스트"""

    def test_returns_end_when_error(self):
        """에러 있을 때 end 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
            error_code=ErrorCode.LLM_API_ERROR,
        )

        result = should_evaluate(state)

        assert result == "end"

    def test_returns_evaluate_when_no_error(self):
        """에러 없을 때 evaluate 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
        )

        result = should_evaluate(state)

        assert result == "evaluate"


class TestShouldRetry:
    """should_retry 조건 함수 테스트"""

    def setup_method(self):
        """각 테스트 전에 should_retry 함수 생성"""
        self.should_retry = make_should_retry(max_retries=2, retry_node="generate")

    def test_returns_end_when_error(self):
        """에러 있을 때 end 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
            error_code=ErrorCode.GENERATE_ERROR,
        )

        assert self.should_retry(state) == "end"

    def test_returns_end_when_pass(self):
        """평가 통과 시 end 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
            evaluation="pass",
            retry_count=0,
        )

        assert self.should_retry(state) == "end"

    def test_returns_generate_when_fail_and_can_retry(self):
        """평가 실패 + 재시도 가능 시 generate 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
            evaluation="fail",
            retry_count=0,
        )

        assert self.should_retry(state) == "generate"

    def test_returns_end_when_max_retries_reached(self):
        """최대 재시도 도달 시 end 반환"""
        state = ResumeState(
            request=ResumeRequest(
                repo_urls=["https://github.com/test/repo"],
                position="개발자",
            ),
            evaluation="fail",
            retry_count=2,
        )

        assert self.should_retry(state) == "end"
