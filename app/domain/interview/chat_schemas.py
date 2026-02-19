from pydantic import BaseModel


class ChatOutput(BaseModel):
    """LLM 구조화 출력 - 면접 채팅 응답"""

    message: str
    follow_up_question: str | None = None
