import httpx

from app.core.exceptions import ErrorCode
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_error_state(
    state: dict,
    error_code: ErrorCode | str,
    error_message: str,
    **additional_fields,
) -> dict:
    """에러 상태를 포함한 새 상태 반환"""
    return {
        **state,
        "error_code": error_code,
        "error_message": error_message,
        **additional_fields,
    }


GITHUB_STATUS_CODE_MAP = {
    401: (ErrorCode.GITHUB_UNAUTHORIZED, "인증 실패 - GitHub 토큰을 확인해주세요"),
    403: (ErrorCode.RATE_LIMIT_EXCEEDED, "API 요청 한도 초과"),
    404: (ErrorCode.GITHUB_NOT_FOUND, "레포지토리를 찾을 수 없습니다"),
}


def handle_http_error(
    e: httpx.HTTPStatusError,
    state: dict,
    node_name: str,
    error_code: ErrorCode | str,
    error_label: str,
    **additional_fields,
) -> dict:
    """HTTPStatusError를 에러 상태로 변환"""
    status_code = e.response.status_code
    logger.error("HTTP 오류", node=node_name, status=status_code)

    if error_code == ErrorCode.GITHUB_API_ERROR and status_code in GITHUB_STATUS_CODE_MAP:
        mapped_code, mapped_message = GITHUB_STATUS_CODE_MAP[status_code]
        return create_error_state(
            state,
            mapped_code,
            mapped_message,
            **additional_fields,
        )

    return create_error_state(
        state,
        error_code,
        f"{error_label}: HTTP {status_code}",
        **additional_fields,
    )


def handle_data_error(
    e: ValueError | KeyError | TypeError,
    state: dict,
    node_name: str,
    error_code: ErrorCode | str,
    error_label: str,
    **additional_fields,
) -> dict:
    """ValueError/KeyError/TypeError를 에러 상태로 변환"""
    logger.error("데이터 오류", node=node_name, error=str(e), exc_info=True)
    return create_error_state(
        state,
        error_code,
        f"{error_label}: {e}",
        **additional_fields,
    )


def handle_connection_error(
    e: httpx.ConnectError | httpx.TimeoutException,
    state: dict,
    node_name: str,
    error_code: ErrorCode | str,
    **additional_fields,
) -> dict:
    """ConnectError/TimeoutException을 에러 상태로 변환"""
    error_type = "연결 실패" if isinstance(e, httpx.ConnectError) else "요청 타임아웃"
    logger.error(error_type, node=node_name)
    return create_error_state(
        state,
        error_code,
        error_type,
        **additional_fields,
    )
