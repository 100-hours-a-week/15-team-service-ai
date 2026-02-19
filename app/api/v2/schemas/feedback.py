from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "InterviewEndMessage",
    "InterviewEndRequest",
    "InterviewEndFeedbackItem",
    "InterviewEndOverallFeedback",
    "InterviewEndErrorResponse",
    "InterviewEndResponse",
]


class InterviewEndMessage(BaseModel):
    """면접 종료 요청 - 개별 메시지"""

    model_config = ConfigDict(populate_by_name=True)

    turn_no: int = Field(alias="turnNo", gt=0)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=5000)
    answer_input_type: str = Field(alias="answerInputType")
    asked_at: str = Field(alias="askedAt")
    answered_at: str = Field(alias="answeredAt")


class InterviewEndRequest(BaseModel):
    """면접 종료 최상위 요청 - 백엔드 팀 형식"""

    model_config = ConfigDict(populate_by_name=True)

    ai_session_id: str = Field(alias="aiSessionId", min_length=1)
    interview_type: Literal["TECHNICAL", "BEHAVIORAL"] = Field(alias="interviewType")
    position: str = Field(min_length=1, max_length=100)
    company: str = Field(min_length=1, max_length=100)
    messages: list[InterviewEndMessage] = Field(min_length=1)


class InterviewEndFeedbackItem(BaseModel):
    """개별 피드백 결과"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    turn_no: int = Field(alias="turnNo")
    score: int = Field(ge=1, le=10)
    strengths: list[str]
    improvements: list[str]
    model_answer: str = Field(alias="modelAnswer")


class InterviewEndOverallFeedback(BaseModel):
    """종합 피드백 결과"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    overall_score: int = Field(alias="overallScore", ge=1, le=10)
    summary: str
    key_strengths: list[str] = Field(alias="keyStrengths")
    key_improvements: list[str] = Field(alias="keyImprovements")


class InterviewEndErrorResponse(BaseModel):
    """에러 정보"""

    code: str
    message: str


class InterviewEndResponse(BaseModel):
    """면접 종료 응답 - 개별 + 종합 피드백 통합"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    status: Literal["success", "failed"]
    feedbacks: list[InterviewEndFeedbackItem] | None = None
    overall_feedback: InterviewEndOverallFeedback | None = Field(
        default=None, alias="overallFeedback"
    )
    error: InterviewEndErrorResponse | None = None
