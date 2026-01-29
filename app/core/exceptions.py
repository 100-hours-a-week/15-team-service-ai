from enum import Enum

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings


class ErrorCode(str, Enum):
    """에러 코드 열거형"""

    GITHUB_UNAUTHORIZED = "GITHUB_UNAUTHORIZED"
    GITHUB_NOT_FOUND = "GITHUB_NOT_FOUND"
    GITHUB_ERROR = "GITHUB_ERROR"
    LLM_ERROR = "LLM_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    GENERATION_FAILED = "GENERATION_FAILED"

    COLLECT_DATA_FAILED = "COLLECT_DATA_FAILED"
    GITHUB_API_ERROR = "GITHUB_API_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    DATA_PARSE_ERROR = "DATA_PARSE_ERROR"
    GENERATE_ERROR = "GENERATE_ERROR"
    LLM_API_ERROR = "LLM_API_ERROR"
    GENERATE_VALIDATION_ERROR = "GENERATE_VALIDATION_ERROR"
    GENERATE_PARSE_ERROR = "GENERATE_PARSE_ERROR"


class CustomException(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode | str,
        message: str,
        detail: str | None = None,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.detail = detail
        super().__init__(message)


class GitHubAPIError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=502,
            error_code=ErrorCode.GITHUB_API_ERROR,
            message="GitHub API 호출에 실패했습니다",
            detail=detail,
        )


class LLMError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=502,
            error_code=ErrorCode.LLM_ERROR,
            message="LLM 호출에 실패했습니다",
            detail=detail,
        )


class ValidationError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.INVALID_INPUT,
            message="입력값이 올바르지 않습니다",
            detail=detail,
        )


class CallbackError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=502,
            error_code=ErrorCode.INTERNAL_ERROR,
            message="콜백 전송에 실패했습니다",
            detail=detail,
        )


def register_exception_handlers(app):
    @app.exception_handler(CustomException)
    async def custom_exception_handler(request: Request, exc: CustomException):
        content = {
            "error_code": exc.error_code,
            "message": exc.message,
        }
        if exc.detail and not settings.is_production:
            content["detail"] = exc.detail

        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )
