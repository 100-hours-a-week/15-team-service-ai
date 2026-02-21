from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """면접 채팅 요청"""

    model_config = ConfigDict(populate_by_name=True)

    ai_session_id: str = Field(alias="aiSessionId", min_length=1)
    question_id: str = Field(alias="questionId", min_length=1)
    answer: str = Field(min_length=1, max_length=5000)


class ChatErrorResponse(BaseModel):
    """채팅 에러 응답"""

    code: str
    message: str


class ChatResponse(BaseModel):
    """면접 채팅 응답"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    status: Literal["success", "failed"]
    message: str | None = None
    follow_up_question: str | None = Field(default=None, alias="followUpQuestion")
    turn_number: int | None = Field(default=None, alias="turnNumber")
    error: ChatErrorResponse | None = None
