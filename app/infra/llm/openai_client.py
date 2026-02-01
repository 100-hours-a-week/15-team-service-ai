from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.infra.llm.base import BaseLLMClient


class OpenAIClient(BaseLLMClient):
    """OpenAI API 클라이언트 - 개발/테스트용"""

    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

        self._model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout,
        )

    def get_chat_model(self) -> BaseChatModel:
        """LangChain ChatOpenAI 모델 반환"""
        return self._model

    def get_model_name(self) -> str:
        """사용 중인 모델 이름 반환"""
        return settings.openai_model
