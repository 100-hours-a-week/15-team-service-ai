"""워크플로우 노드 함수 테스트"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import ErrorCode
from app.domain.resume.schemas import (
    EvaluationOutput,
    ResumeRequest,
    ResumeState,
    UserStats,
)
from app.domain.resume.workflow import (
    collect_data_node,
    evaluate_node,
    generate_node,
    should_continue,
    should_evaluate,
    should_retry,
)


class TestCollectDataNode:
    """collect_data_node 함수 테스트"""

    @pytest.fixture
    def collect_state(self, sample_resume_request) -> ResumeState:
        """데이터 수집 노드용 상태"""
        return ResumeState(request=sample_resume_request, job_id="test-job-123")

    @pytest.mark.asyncio
    async def test_collect_data_success(
        self, collect_state, sample_project_info, sample_repo_contexts
    ):
        """정상 데이터 수집"""
        mock_user_stats = UserStats(total_commits=100, total_prs=10, total_issues=5)

        with (
            patch(
                "app.domain.resume.workflow.collect_project_info",
                new_callable=AsyncMock,
                return_value=sample_project_info,
            ),
            patch(
                "app.domain.resume.workflow.collect_repo_contexts",
                new_callable=AsyncMock,
                return_value=sample_repo_contexts,
            ),
            patch(
                "app.domain.resume.workflow.collect_user_stats",
                new_callable=AsyncMock,
                return_value=mock_user_stats,
            ),
        ):
            result = await collect_data_node(collect_state)

        assert result["project_info"] == sample_project_info
        assert result["repo_contexts"] == sample_repo_contexts
        assert result["user_stats"] == mock_user_stats
        assert result["retry_count"] == 0
        assert result.get("error_code") is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error,expected_code,expected_msg_part",
        [
            (None, ErrorCode.COLLECT_DATA_FAILED, "프로젝트 정보 수집 실패"),
            (
                httpx.HTTPStatusError(
                    "Unauthorized",
                    request=httpx.Request("GET", "test"),
                    response=httpx.Response(401, request=httpx.Request("GET", "test")),
                ),
                ErrorCode.GITHUB_API_ERROR,
                "HTTP 401",
            ),
            (ValueError("Invalid URL format"), ErrorCode.INVALID_INPUT, "잘못된 입력값"),
        ],
        ids=["empty_project_info", "github_api_error", "invalid_url"],
    )
    async def test_collect_data_errors(
        self, collect_state, error, expected_code, expected_msg_part
    ):
        """다양한 에러 상황 테스트"""
        if error is None:
            mock_return = []
            mock_side_effect = None
        else:
            mock_return = None
            mock_side_effect = error

        with (
            patch(
                "app.domain.resume.workflow.collect_project_info",
                new_callable=AsyncMock,
                return_value=mock_return,
                side_effect=mock_side_effect,
            ),
            patch(
                "app.domain.resume.workflow.collect_repo_contexts",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await collect_data_node(collect_state)

        assert result["error_code"] == expected_code
        assert expected_msg_part in result["error_message"]


class TestGenerateNode:
    """generate_node 함수 테스트"""

    @pytest.fixture
    def generate_state(self, sample_resume_request, sample_project_info) -> ResumeState:
        """생성 노드용 상태"""
        return ResumeState(
            request=sample_resume_request,
            job_id="test-job-123",
            project_info=sample_project_info,
            repo_contexts={},
            retry_count=0,
        )

    @pytest.mark.asyncio
    async def test_generate_success(self, generate_state, sample_resume_data):
        """정상 이력서 생성"""
        with patch(
            "app.domain.resume.workflow._generate_in_batches",
            new_callable=AsyncMock,
            return_value=sample_resume_data,
        ):
            result = await generate_node(generate_state)

        assert result["resume_data"] == sample_resume_data
        assert result.get("error_code") is None

    @pytest.mark.asyncio
    async def test_generate_no_project_info(self, generate_state):
        """project_info가 없을 때 에러 상태 설정"""
        state_without_project = dict(generate_state)
        state_without_project["project_info"] = None

        result = await generate_node(state_without_project)

        assert result["error_code"] == ErrorCode.GENERATE_ERROR
        assert "프로젝트 정보가 없습니다" in result["error_message"]

    @pytest.mark.asyncio
    async def test_generate_retry_increments_count(self, generate_state, sample_resume_data):
        """재시도 시 retry_count 증가"""
        state_with_fail = dict(generate_state)
        state_with_fail["evaluation"] = "fail"
        state_with_fail["retry_count"] = 1

        with patch(
            "app.domain.resume.workflow._generate_in_batches",
            new_callable=AsyncMock,
            return_value=sample_resume_data,
        ):
            result = await generate_node(state_with_fail)

        assert result["retry_count"] == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error,expected_code,expected_msg_part",
        [
            (
                httpx.HTTPStatusError(
                    "Server Error",
                    request=httpx.Request("POST", "test"),
                    response=httpx.Response(500, request=httpx.Request("POST", "test")),
                ),
                ErrorCode.LLM_API_ERROR,
                "HTTP 500",
            ),
            (ValueError("Invalid format"), ErrorCode.GENERATE_VALIDATION_ERROR, "검증 오류"),
        ],
        ids=["llm_api_error", "validation_error"],
    )
    async def test_generate_errors(
        self, generate_state, error, expected_code, expected_msg_part
    ):
        """생성 노드 에러 테스트"""
        with patch(
            "app.domain.resume.workflow._generate_in_batches",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            result = await generate_node(generate_state)

        assert result["error_code"] == expected_code
        assert expected_msg_part in result["error_message"]


class TestEvaluateNode:
    """evaluate_node 함수 테스트"""

    @pytest.fixture
    def evaluate_state(self, sample_resume_request, sample_resume_data) -> ResumeState:
        """평가 노드용 상태"""
        return ResumeState(
            request=sample_resume_request,
            job_id="test-job-123",
            resume_data=sample_resume_data,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "eval_result,violated_rule,feedback",
        [
            ("pass", None, "이력서가 모든 기준을 충족합니다"),
            ("fail", 2, "기술 스택이 부족합니다"),
        ],
        ids=["pass", "fail"],
    )
    async def test_evaluate_results(
        self, evaluate_state, eval_result, violated_rule, feedback
    ):
        """평가 결과 처리 테스트"""
        mock_evaluation = EvaluationOutput(
            result=eval_result,
            violated_rule=violated_rule,
            violated_item="tech_stack" if violated_rule else None,
            feedback=feedback,
        )

        with patch(
            "app.domain.resume.workflow.evaluate_resume",
            new_callable=AsyncMock,
            return_value=mock_evaluation,
        ):
            result = await evaluate_node(evaluate_state)

        assert result["evaluation"] == eval_result
        assert result["evaluation_feedback"] == feedback

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error",
        [
            httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("POST", "test"),
                response=httpx.Response(500, request=httpx.Request("POST", "test")),
            ),
            ValueError("Parse error"),
        ],
        ids=["http_error", "value_error"],
    )
    async def test_evaluate_error_returns_pass(self, evaluate_state, error):
        """평가 오류 시 관용적으로 pass 처리"""
        with patch(
            "app.domain.resume.workflow.evaluate_resume",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            result = await evaluate_node(evaluate_state)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == ""


class TestConditionFunctions:
    """조건 함수 테스트"""

    @pytest.mark.parametrize(
        "error_code,expected",
        [
            (ErrorCode.GITHUB_API_ERROR, "end"),
            (None, "generate"),
        ],
        ids=["with_error", "no_error"],
    )
    def test_should_continue(self, sample_resume_request, error_code, expected):
        """should_continue 조건 테스트"""
        state = ResumeState(
            request=sample_resume_request,
            error_code=error_code,
            error_message="Error" if error_code else "",
        )

        result = should_continue(state)

        assert result == expected

    @pytest.mark.parametrize(
        "error_code,expected",
        [
            (ErrorCode.LLM_API_ERROR, "end"),
            (None, "evaluate"),
        ],
        ids=["with_error", "no_error"],
    )
    def test_should_evaluate(self, sample_resume_request, error_code, expected):
        """should_evaluate 조건 테스트"""
        state = ResumeState(request=sample_resume_request, error_code=error_code)

        result = should_evaluate(state)

        assert result == expected

    @pytest.mark.parametrize(
        "error_code,evaluation,retry_count,max_retries,expected",
        [
            (ErrorCode.GENERATE_ERROR, None, 0, 3, "end"),
            (None, "pass", 0, 3, "end"),
            (None, "fail", 0, 3, "generate"),
            (None, "fail", 3, 3, "end"),
        ],
        ids=["with_error", "pass", "fail_can_retry", "max_retries_reached"],
    )
    def test_should_retry(
        self, sample_resume_request, error_code, evaluation, retry_count, max_retries, expected
    ):
        """should_retry 조건 테스트"""
        state = ResumeState(
            request=sample_resume_request,
            error_code=error_code,
            evaluation=evaluation,
            retry_count=retry_count,
        )

        with patch("app.domain.resume.workflow.settings") as mock_settings:
            mock_settings.workflow_max_retries = max_retries
            result = should_retry(state)

        assert result == expected
