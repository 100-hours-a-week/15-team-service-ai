"""워크플로우 에러 처리 헬퍼 테스트"""

from unittest.mock import MagicMock

import httpx

from app.core.exceptions import ErrorCode
from app.domain.resume.error_handler import (
    create_error_state,
    handle_data_error,
    handle_http_error,
)


def _make_base_state():
    return {
        "request": MagicMock(),
        "job_id": "test-job",
    }


class TestCreateErrorState:
    def test_basic_error_state(self):
        state = _make_base_state()
        result = create_error_state(state, "TEST_ERROR", "테스트 에러")

        assert result["error_code"] == "TEST_ERROR"
        assert result["error_message"] == "테스트 에러"
        assert result["job_id"] == "test-job"

    def test_additional_fields(self):
        state = _make_base_state()
        result = create_error_state(
            state,
            "TEST_ERROR",
            "테스트 에러",
            retry_count=2,
        )

        assert result["retry_count"] == 2


class TestHandleHttpError:
    def test_http_error_with_additional_fields(self):
        state = _make_base_state()
        response = MagicMock()
        response.status_code = 500
        error = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=response,
        )

        result = handle_http_error(
            error,
            state,
            "test_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
            retry_count=1,
        )

        assert result["error_code"] == ErrorCode.LLM_API_ERROR
        assert result["retry_count"] == 1

    def test_github_401_maps_to_unauthorized(self):
        state = _make_base_state()
        response = MagicMock()
        response.status_code = 401
        error = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=response,
        )

        result = handle_http_error(
            error,
            state,
            "collect_node",
            ErrorCode.GITHUB_API_ERROR,
            "GitHub API 오류",
        )

        assert result["error_code"] == ErrorCode.GITHUB_UNAUTHORIZED
        assert "인증 실패" in result["error_message"]

    def test_github_403_maps_to_rate_limit(self):
        state = _make_base_state()
        response = MagicMock()
        response.status_code = 403
        error = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=response,
        )

        result = handle_http_error(
            error,
            state,
            "collect_node",
            ErrorCode.GITHUB_API_ERROR,
            "GitHub API 오류",
        )

        assert result["error_code"] == ErrorCode.RATE_LIMIT_EXCEEDED
        assert "요청 한도" in result["error_message"]

    def test_github_404_maps_to_not_found(self):
        state = _make_base_state()
        response = MagicMock()
        response.status_code = 404
        error = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=response,
        )

        result = handle_http_error(
            error,
            state,
            "collect_node",
            ErrorCode.GITHUB_API_ERROR,
            "GitHub API 오류",
        )

        assert result["error_code"] == ErrorCode.GITHUB_NOT_FOUND
        assert "찾을 수 없습니다" in result["error_message"]

    def test_llm_error_skips_github_mapping(self):
        state = _make_base_state()
        response = MagicMock()
        response.status_code = 401
        error = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=response,
        )

        result = handle_http_error(
            error,
            state,
            "generate_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
        )

        assert result["error_code"] == ErrorCode.LLM_API_ERROR
        assert "HTTP 401" in result["error_message"]


class TestHandleDataError:
    def test_key_error_to_state(self):
        state = _make_base_state()
        error = KeyError("missing_key")

        result = handle_data_error(
            error,
            state,
            "test_node",
            ErrorCode.DATA_PARSE_ERROR,
            "데이터 파싱 오류",
        )

        assert result["error_code"] == ErrorCode.DATA_PARSE_ERROR
        assert "missing_key" in result["error_message"]

    def test_type_error_to_state(self):
        state = _make_base_state()
        error = TypeError("unexpected type")

        result = handle_data_error(
            error,
            state,
            "test_node",
            ErrorCode.GENERATE_PARSE_ERROR,
            "이력서 생성 중 데이터 오류",
            retry_count=2,
        )

        assert result["error_code"] == ErrorCode.GENERATE_PARSE_ERROR
        assert "unexpected type" in result["error_message"]
        assert result["retry_count"] == 2
