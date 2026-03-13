import operator
from typing import Annotated, TypedDict

from pydantic import BaseModel


class ChatMessage(TypedDict):
    """대화 메시지 한 건 - role은 human 또는 ai"""

    role: str
    content: str


class ChatState(TypedDict, total=False):
    """멀티턴 채팅 워크플로우 상태

    messages는 Annotated[list, operator.add]로 선언하여
    노드가 반환하는 메시지가 기존 이력에 누적됩니다
    """

    resume_json: str
    position: str
    interview_type: str
    question_text: str
    question_intent: str
    related_project: str | None
    session_id: str | None
    messages: Annotated[list[ChatMessage], operator.add]
    last_response: str | None
    last_follow_up: str | None
    last_follow_up_intent: str | None
    turn_count: int
    error_message: str | None


MAX_CHAT_TURNS = 10
MAX_FOLLOW_UP_TURNS = 4


class ChatOutput(BaseModel):
    """LLM 구조화 출력 - 면접 채팅 응답"""

    message: str
    follow_up_question: str | None = None
    follow_up_intent: str | None = None
