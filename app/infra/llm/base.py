import functools
import os

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)


def setup_langfuse_env() -> None:
    """Langfuse 환경 변수 설정"""
    if settings.langfuse_public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    if settings.langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    if settings.langfuse_base_url:
        os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url


def get_langfuse_handler() -> CallbackHandler | None:
    """Langfuse 콜백 핸들러 반환"""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    return CallbackHandler()


@functools.cache
def get_generator_llm() -> ChatOpenAI:
    """vLLM 클라이언트 반환"""
    return ChatOpenAI(
        model=settings.vllm_model,
        api_key=settings.vllm_api_key or "EMPTY",
        base_url=settings.vllm_base_url,
        timeout=settings.vllm_timeout,
        max_retries=2,
        temperature=0.2,
        max_tokens=16384,
    )


@functools.cache
def get_evaluator_llm() -> ChatGoogleGenerativeAI:
    """Gemini 클라이언트 반환"""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_evaluator_model,
        google_api_key=settings.gemini_api_key,
        timeout=settings.gemini_timeout,
        max_retries=2,
        temperature=1.0,
        thinking_budget=2048,
    )


def _build_langfuse_config(session_id: str | None, tags: list[str]) -> dict:
    """Langfuse 콜백 설정 생성"""
    langfuse_handler = get_langfuse_handler()
    return {
        "callbacks": [langfuse_handler] if langfuse_handler else [],
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_tags": tags,
        },
    }


async def _invoke_llm[T](
    llm: BaseChatModel,
    output_type: type[T],
    system_prompt: str,
    human_content: str,
    config: dict,
    structured_output_method: str | None = None,
) -> T:
    """구조화된 출력으로 LLM 호출"""
    kwargs = {}
    if structured_output_method:
        kwargs["method"] = structured_output_method
    structured_llm = llm.with_structured_output(output_type, **kwargs)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]
    try:
        return await structured_llm.ainvoke(messages, config=config)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
        raise
    except Exception as e:
        logger.error(
            "LLM 출력 파싱 실패",
            output_type=output_type.__name__,
            error_type=type(e).__name__,
            error=str(e),
            exc_info=True,
        )
        raise LLMError(detail=f"LLM 출력 파싱 실패 [{type(e).__name__}]: {e}") from e
