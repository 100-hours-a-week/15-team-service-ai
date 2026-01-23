from fastapi import Request
from fastapi.responses import JSONResponse


class CustomException(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
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
            error_code="GITHUB_API_ERROR",
            message="GitHub API 호출에 실패했습니다",
            detail=detail,
        )


class LLMError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=502,
            error_code="LLM_ERROR",
            message="LLM 호출에 실패했습니다",
            detail=detail,
        )


class ValidationError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=400,
            error_code="VALIDATION_ERROR",
            message="입력값이 올바르지 않습니다",
            detail=detail,
        )


class CallbackError(CustomException):
    def __init__(self, detail: str | None = None):
        super().__init__(
            status_code=502,
            error_code="CALLBACK_ERROR",
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
        if exc.detail:
            content["detail"] = exc.detail

        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )
