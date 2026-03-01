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


def _get_local_fallback(name: str, **variables: str) -> str:
    """Langfuse 조회 실패 시 로컬 상수로 fallback"""
    from app.domain.resume.prompts.evaluation import RESUME_EVALUATOR_HUMAN, RESUME_EVALUATOR_SYSTEM
    from app.domain.resume.prompts.generation import (
        RESUME_GENERATOR_HUMAN,
        RESUME_GENERATOR_RETRY_HUMAN,
        RESUME_GENERATOR_SYSTEM,
    )
    from app.domain.resume.prompts.plan import RESUME_PLAN_HUMAN, RESUME_PLAN_SYSTEM

    registry: dict[str, str] = {
        "resume-evaluator-system": RESUME_EVALUATOR_SYSTEM,
        "resume-evaluator-human": RESUME_EVALUATOR_HUMAN,
        "resume-plan-system": RESUME_PLAN_SYSTEM,
        "resume-plan-human": RESUME_PLAN_HUMAN,
        "resume-generator-system": RESUME_GENERATOR_SYSTEM,
        "resume-generator-human": RESUME_GENERATOR_HUMAN,
        "resume-generator-retry-human": RESUME_GENERATOR_RETRY_HUMAN,
    }

    if name not in registry:
        raise LLMError(detail=f"프롬프트 조회 실패 및 fallback 없음: {name}")

    logger.warning("로컬 fallback 프롬프트 사용", prompt_name=name)
    return registry[name].format(**variables)


def get_prompt(name: str, **variables: str) -> str:
    """Langfuse에서 프롬프트 조회 후 변수 치환, 실패 시 로컬 fallback

    name: Langfuse에 등록된 프롬프트 이름
    variables: 프롬프트에 주입할 변수들
    """
    client = _get_client()

    try:
        prompt = client.get_prompt(name)
    except Exception as e:
        logger.warning("Langfuse 프롬프트 조회 실패, fallback 시도", prompt_name=name, error=str(e))
        return _get_local_fallback(name, **variables)

    try:
        compiled = prompt.compile(**variables)
    except KeyError as e:
        logger.error("프롬프트 변수 누락", prompt_name=name, variable=str(e), exc_info=True)
        raise LLMError(detail=f"프롬프트 '{name}'에 필요한 변수 누락: {e}") from e

    logger.debug("Langfuse 프롬프트 사용", prompt_name=name)
    return compiled
