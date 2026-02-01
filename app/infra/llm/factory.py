from typing import Literal

from app.core.config import settings
from app.core.logging import get_logger
from app.infra.llm.base import BaseLLMClient
from app.infra.llm.gemini_client import GeminiClient
from app.infra.llm.openai_client import OpenAIClient
from app.infra.llm.vllm_client import VLLMClient

logger = get_logger(__name__)

LLMProvider = Literal["openai", "vllm"]

_generator_client: BaseLLMClient | None = None
_evaluator_client: BaseLLMClient | None = None


def get_generator_client() -> BaseLLMClient:
    """이력서 생성용 LLM 클라이언트 반환"""
    global _generator_client

    if _generator_client is not None:
        return _generator_client

    provider = settings.llm_provider

    if provider == "openai":
        _generator_client = OpenAIClient()
        logger.info("OpenAI 클라이언트 초기화 model=%s", settings.openai_model)
    elif provider == "vllm":
        _generator_client = VLLMClient()
        logger.info("vLLM 클라이언트 초기화 model=%s", settings.vllm_model)
    else:
        raise ValueError(f"지원하지 않는 LLM 프로바이더: {provider}")

    return _generator_client


def get_evaluator_client() -> BaseLLMClient:
    """이력서 평가용 LLM 클라이언트 반환"""
    global _evaluator_client

    if _evaluator_client is not None:
        return _evaluator_client

    _evaluator_client = GeminiClient()
    logger.info("Gemini 클라이언트 초기화 model=%s", settings.gemini_model)

    return _evaluator_client


def reset_clients() -> None:
    """클라이언트 캐시 초기화 - 테스트용"""
    global _generator_client, _evaluator_client
    _generator_client = None
    _evaluator_client = None
