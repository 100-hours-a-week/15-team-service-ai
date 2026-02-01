from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.infra.llm.base import BaseLLMClient


class GeminiClient(BaseLLMClient):
    """Gemini 클라이언트 - 이력서 평가용"""

    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다")

        self._model = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            timeout=settings.gemini_timeout,
        )

    def get_chat_model(self) -> BaseChatModel:
        """LangChain ChatGoogleGenerativeAI 모델 반환"""
        return self._model

    def get_model_name(self) -> str:
        """사용 중인 모델 이름 반환"""
        return settings.gemini_model
