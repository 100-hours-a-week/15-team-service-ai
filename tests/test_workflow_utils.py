from unittest.mock import AsyncMock

import httpx

from app.domain.resume.workflow_utils import (
    evaluate_with_fallback,
    has_error,
    make_should_retry,
    should_evaluate,
)


class TestHasError:
    """has_error 함수 테스트"""

    def test_returns_true_when_error_code_exists(self):
        """error_code가 있으면 True 반환"""
        state = {"error_code": "SOME_ERROR", "error_message": "에러 발생"}
        assert has_error(state, "test") is True

    def test_returns_false_when_no_error_code(self):
        """error_code가 없으면 False 반환"""
        state = {"retry_count": 0}
        assert has_error(state, "test") is False

    def test_returns_false_when_error_code_is_empty(self):
        """error_code가 빈 문자열이면 False 반환"""
        state = {"error_code": ""}
        assert has_error(state, "test") is False

    def test_returns_false_when_error_code_is_none(self):
        """error_code가 None이면 False 반환"""
        state = {"error_code": None}
        assert has_error(state, "test") is False


class TestShouldEvaluate:
    """should_evaluate 함수 테스트"""

    def test_returns_evaluate_when_no_error(self):
        """에러 없으면 evaluate 반환"""
        state = {"retry_count": 0}
        assert should_evaluate(state) == "evaluate"

    def test_returns_end_when_error(self):
        """에러 있으면 end 반환"""
        state = {"error_code": "LLM_ERROR"}
        assert should_evaluate(state) == "end"


class TestMakeShouldRetry:
    """make_should_retry 함수 테스트"""

    def test_returns_end_when_error(self):
        """에러 있으면 end 반환"""
        should_retry = make_should_retry(max_retries=2, retry_node="generate")
        state = {"error_code": "SOME_ERROR"}
        assert should_retry(state) == "end"

    def test_returns_end_when_pass(self):
        """평가 통과 시 end 반환"""
        should_retry = make_should_retry(max_retries=2, retry_node="generate")
        state = {"evaluation": "pass", "retry_count": 0}
        assert should_retry(state) == "end"

    def test_returns_retry_node_when_fail_and_can_retry(self):
        """평가 실패 + 재시도 가능하면 retry_node 반환"""
        should_retry = make_should_retry(max_retries=2, retry_node="generate")
        state = {"evaluation": "fail", "retry_count": 0}
        assert should_retry(state) == "generate"

    def test_returns_end_when_max_retries_reached(self):
        """최대 재시도 도달 시 end 반환"""
        should_retry = make_should_retry(max_retries=2, retry_node="generate")
        state = {"evaluation": "fail", "retry_count": 2}
        assert should_retry(state) == "end"

    def test_returns_end_when_retry_count_exceeds_max(self):
        """재시도 횟수가 최대를 초과하면 end 반환"""
        should_retry = make_should_retry(max_retries=1, retry_node="edit")
        state = {"evaluation": "fail", "retry_count": 3}
        assert should_retry(state) == "end"

    def test_custom_retry_node_name(self):
        """커스텀 retry_node 이름 반환"""
        should_retry = make_should_retry(max_retries=2, retry_node="edit")
        state = {"evaluation": "fail", "retry_count": 0}
        assert should_retry(state) == "edit"

    def test_default_evaluation_is_pass(self):
        """evaluation이 없으면 기본값 pass로 end 반환"""
        should_retry = make_should_retry(max_retries=2, retry_node="generate")
        state = {"retry_count": 0}
        assert should_retry(state) == "end"


class TestEvaluateWithFallback:
    """evaluate_with_fallback 함수 테스트"""

    async def test_success(self):
        """평가 성공 시 결과 반환"""
        mock_result = AsyncMock()
        mock_result.result = "pass"
        mock_result.feedback = "좋은 이력서입니다"

        evaluate_fn = AsyncMock(return_value=mock_result)
        state = {"resume_data": "some_data"}

        result = await evaluate_with_fallback(state, evaluate_fn)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == "좋은 이력서입니다"

    async def test_fail_result(self):
        """평가 실패 결과도 정상 반환"""
        mock_result = AsyncMock()
        mock_result.result = "fail"
        mock_result.feedback = "기술 스택이 부족합니다"

        evaluate_fn = AsyncMock(return_value=mock_result)
        state = {"resume_data": "some_data"}

        result = await evaluate_with_fallback(state, evaluate_fn)

        assert result["evaluation"] == "fail"
        assert result["evaluation_feedback"] == "기술 스택이 부족합니다"

    async def test_timeout_returns_pass(self):
        """타임아웃 시 pass로 폴백"""
        evaluate_fn = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        state = {"resume_data": "some_data"}

        result = await evaluate_with_fallback(state, evaluate_fn)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == ""

    async def test_connect_error_returns_pass(self):
        """연결 오류 시 pass로 폴백"""
        evaluate_fn = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
        state = {"resume_data": "some_data"}

        result = await evaluate_with_fallback(state, evaluate_fn)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == ""

    async def test_http_status_error_returns_pass(self):
        """HTTP 오류 시 pass로 폴백"""
        mock_response = httpx.Response(500, request=httpx.Request("POST", "test"))
        evaluate_fn = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=mock_response.request,
                response=mock_response,
            )
        )
        state = {"resume_data": "some_data"}

        result = await evaluate_with_fallback(state, evaluate_fn)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == ""

    async def test_value_error_returns_pass(self):
        """파싱 오류 시 pass로 폴백"""
        evaluate_fn = AsyncMock(side_effect=ValueError("parse error"))
        state = {"resume_data": "some_data"}

        result = await evaluate_with_fallback(state, evaluate_fn)

        assert result["evaluation"] == "pass"
        assert result["evaluation_feedback"] == ""

    async def test_preserves_existing_state(self):
        """기존 상태가 유지되는지 확인"""
        mock_result = AsyncMock()
        mock_result.result = "pass"
        mock_result.feedback = "OK"

        evaluate_fn = AsyncMock(return_value=mock_result)
        state = {"resume_data": "some_data", "retry_count": 1, "request": "req"}

        result = await evaluate_with_fallback(state, evaluate_fn)

        assert result["retry_count"] == 1
        assert result["request"] == "req"
        assert result["evaluation"] == "pass"
