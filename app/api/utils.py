import asyncio

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def send_callback_with_retry(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    job_id: str,
) -> bool:
    """콜백 전송, 실패 시 지수 백오프로 재시도"""
    max_retries = settings.callback_max_retries
    base_delay = settings.callback_retry_base_delay

    for attempt in range(max_retries):
        try:
            headers = {"X-AI-Callback-Secret": settings.ai_callback_secret}
            response = await client.post(url, json=payload, headers=headers)

            if 200 <= response.status_code < 300:
                logger.info(
                    "콜백 전송 성공",
                    status_code=response.status_code,
                    attempt=attempt + 1,
                )
                return True

            logger.warning(
                "콜백 응답 오류",
                status_code=response.status_code,
                attempt=attempt + 1,
            )

        except httpx.RequestError as e:
            logger.warning(
                "콜백 요청 실패",
                error=type(e).__name__,
                attempt=attempt + 1,
            )

        if attempt < max_retries - 1:
            delay = base_delay * (2**attempt)
            logger.info("콜백 재시도 대기", delay_seconds=delay)
            await asyncio.sleep(delay)

    logger.error("콜백 전송 최종 실패", max_retries=max_retries)
    return False
