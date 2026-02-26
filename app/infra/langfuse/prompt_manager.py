from langfuse import Langfuse

from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)

_langfuse_client: Langfuse | None = None


def _get_client() -> Langfuse:
    """Langfuse 클라이언트 싱글턴 반환"""
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    _langfuse_client = Langfuse()
    return _langfuse_client


def get_prompt(name: str, **variables: str) -> str:
    """Langfuse에서 프롬프트 조회 후 변수 치환

    name: Langfuse에 등록된 프롬프트 이름
    variables: 프롬프트에 주입할 변수들
    """
    client = _get_client()

    try:
        prompt = client.get_prompt(name)
    except Exception as e:
        logger.error("Langfuse 프롬프트 조회 실패", prompt_name=name, error=str(e), exc_info=True)
        raise LLMError(detail=f"프롬프트 조회 실패: {name}") from e

    try:
        compiled = prompt.compile(**variables)
    except KeyError as e:
        logger.error("프롬프트 변수 누락", prompt_name=name, variable=str(e), exc_info=True)
        raise LLMError(detail=f"프롬프트 '{name}'에 필요한 변수 누락: {e}") from e

    logger.debug("Langfuse 프롬프트 사용", prompt_name=name)
    return compiled
