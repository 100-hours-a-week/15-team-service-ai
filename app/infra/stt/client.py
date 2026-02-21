import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=settings.stt_timeout)
    return _client


async def transcribe_audio(
    file_content: bytes,
    filename: str,
    language: str = "ko",
) -> str:
    """음성 파일을 텍스트로 변환"""
    url = settings.stt_base_url + "/v1/audio/transcriptions"
    client = _get_client()

    try:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.stt_api_key}"},
            files={"file": (filename, file_content)},
            data={"model": settings.stt_model, "language": language},
        )
        response.raise_for_status()
        result = response.json()
        logger.debug("STT 변환 완료", filename=filename, language=language)
        return result["text"]
    except httpx.TimeoutException:
        logger.warning("STT 요청 타임아웃", filename=filename)
        raise
    except httpx.HTTPStatusError as e:
        logger.error(
            "STT 요청 실패",
            filename=filename,
            status_code=e.response.status_code,
            exc_info=True,
        )
        raise
    except Exception:
        logger.error("STT 변환 중 예외 발생", filename=filename, exc_info=True)
        raise
