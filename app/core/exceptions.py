from enum import Enum

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.context import get_request_id
from app.core.logging import get_logger

logger = get_logger(__name__)


class ErrorCode(str, Enum):
    """에러 코드 열거형"""

    GITHUB_UNAUTHORIZED = "GITHUB_UNAUTHORIZED"
    GITHUB_NOT_FOUND = "GITHUB_NOT_FOUND"
    LLM_ERROR = "LLM_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    GENERATION_FAILED = "GENERATION_FAILED"

    COLLECT_DATA_FAILED = "COLLECT_DATA_FAILED"
    GITHUB_API_ERROR = "GITHUB_API_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    DATA_PARSE_ERROR = "DATA_PARSE_ERROR"
    GENERATE_ERROR = "GENERATE_ERROR"
    PLAN_ERROR = "PLAN_ERROR"
    LLM_API_ERROR = "LLM_API_ERROR"
    GENERATE_VALIDATION_ERROR = "GENERATE_VALIDATION_ERROR"
    GENERATE_PARSE_ERROR = "GENERATE_PARSE_ERROR"

    EMPTY_REPOSITORY = "EMPTY_REPOSITORY"
    NO_CONTRIBUTION = "NO_CONTRIBUTION"
    POSITION_MISMATCH = "POSITION_MISMATCH"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    CALLBACK_ERROR = "CALLBACK_ERROR"
    EDIT_FAILED = "EDIT_FAILED"
    EDIT_OUT_OF_SCOPE = "EDIT_OUT_OF_SCOPE"
    INTERVIEW_GENERATE_ERROR = "INTERVIEW_GENERATE_ERROR"
    INTERVIEW_EVALUATE_ERROR = "INTERVIEW_EVALUATE_ERROR"
    FEEDBACK_GENERATE_ERROR = "FEEDBACK_GENERATE_ERROR"
    FEEDBACK_EVALUATE_ERROR = "FEEDBACK_EVALUATE_ERROR"
    CHAT_GENERATE_ERROR = "CHAT_GENERATE_ERROR"
    STT_API_ERROR = "STT_API_ERROR"
    S3_DOWNLOAD_ERROR = "S3_DOWNLOAD_ERROR"
    INVALID_AUDIO_FORMAT = "INVALID_AUDIO_FORMAT"


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
    def __init__(self, status_code: int = 502, detail: str | None = None):
        super().__init__(
            status_code=status_code,
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
            error_code=ErrorCode.CALLBACK_ERROR,
            message="콜백 전송에 실패했습니다",
            detail=detail,
        )


class PositionMismatchError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=400,
            error_code=ErrorCode.POSITION_MISMATCH,
            message="포지션과 기술 스택이 일치하지 않습니다",
            detail=detail,
        )


class STTError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=502,
            error_code=ErrorCode.STT_API_ERROR,
            message="음성 변환에 실패했습니다",
            detail=detail,
        )


class S3DownloadError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=502,
            error_code=ErrorCode.S3_DOWNLOAD_ERROR,
            message="S3 파일 다운로드에 실패했습니다",
            detail=detail,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CustomException)
    async def custom_exception_handler(request: Request, exc: CustomException):
        content = {
            "error_code": exc.error_code,
            "message": exc.message,
            "request_id": get_request_id(),
        }
        if exc.detail and not settings.is_production:
            content["detail"] = exc.detail

        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            field = " -> ".join(str(loc) for loc in error["loc"])
            errors.append({"field": field, "message": error["msg"]})

        content = {
            "error_code": ErrorCode.INVALID_INPUT,
            "message": "요청 데이터가 올바르지 않습니다",
            "request_id": get_request_id(),
        }
        if not settings.is_production:
            content["errors"] = errors

        return JSONResponse(status_code=422, content=content)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": ErrorCode.INTERNAL_ERROR,
                "message": "Internal server error",
                "request_id": get_request_id(),
            },
        )
