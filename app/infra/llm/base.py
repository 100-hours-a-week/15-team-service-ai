from abc import ABC, abstractmethod
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(ABC):
    """LLM 클라이언트 추상 클래스"""

    @abstractmethod
    def get_chat_model(self) -> BaseChatModel:
        """LangChain 호환 채팅 모델 반환"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """사용 중인 모델 이름 반환"""
        pass

    def with_structured_output(self, schema: type[T]) -> BaseChatModel:
        """구조화된 출력을 위한 모델 반환"""
        return self.get_chat_model().with_structured_output(schema)
