"""
HTTP 요청 로깅 미들웨어

- 요청 시작 시 request_id 생성
- 요청/응답 메타데이터 자동 로깅
- X-Request-ID 응답 헤더 추가
"""

import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import clear_context, set_request_id
from app.core.logging import get_logger

logger = get_logger(__name__)

SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class RequestLoggingMiddleware:
    """HTTP 요청 로깅 및 request_id 관리 미들웨어"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}

        incoming_request_id = headers.get("x-request-id")
        request_id = set_request_id(incoming_request_id or None)

        method = scope.get("method", "UNKNOWN")
        client_ip = self._get_client_ip(scope, headers)

        start_time = time.perf_counter()

        logger.info(
            "요청 시작",
            method=method,
            path=path,
            client_ip=client_ip,
        )

        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "요청 완료",
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "요청 실패",
                method=method,
                path=path,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            raise
        finally:
            clear_context()

    def _get_client_ip(self, scope: Scope, headers: dict) -> str:
        """클라이언트 IP 추출"""
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = scope.get("client")
        if client:
            return client[0]
        return "unknown"
