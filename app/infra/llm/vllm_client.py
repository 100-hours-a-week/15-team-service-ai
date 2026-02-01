from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.infra.llm.base import BaseLLMClient


class VLLMClient(BaseLLMClient):
    """vLLM/RunPod 클라이언트 - 운영용"""

    def __init__(self):
        if not settings.vllm_api_url:
            raise ValueError("VLLM_API_URL이 설정되지 않았습니다")

        self._model = ChatOpenAI(
            model=settings.vllm_model,
            api_key=settings.vllm_api_key,
            base_url=settings.vllm_api_url,
            timeout=settings.vllm_timeout,
        )

    def get_chat_model(self) -> BaseChatModel:
        """LangChain ChatOpenAI 모델 반환"""
        return self._model

    def get_model_name(self) -> str:
        """사용 중인 모델 이름 반환"""
        return settings.vllm_model
