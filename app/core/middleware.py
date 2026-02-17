"""
HTTP 요청 로깅 미들웨어

- 요청 시작 시 request_id 생성
- 요청/응답 메타데이터 자동 로깅
- X-Request-ID 응답 헤더 추가
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import clear_context, set_request_id
from app.core.logging import get_logger

logger = get_logger(__name__)

SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """HTTP 요청 로깅 및 request_id 관리 미들웨어"""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        incoming_request_id = request.headers.get("X-Request-ID")
        request_id = set_request_id(incoming_request_id)

        start_time = time.perf_counter()

        logger.info(
            "요청 시작",
            method=request.method,
            path=request.url.path,
            client_ip=self._get_client_ip(request),
        )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "요청 완료",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "요청 실패",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            raise

        finally:
            clear_context()

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
