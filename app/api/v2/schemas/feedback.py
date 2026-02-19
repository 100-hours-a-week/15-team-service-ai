from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "FeedbackRequest",
    "FeedbackResult",
    "FeedbackErrorResponse",
    "FeedbackResponse",
    "OverallAnswerItem",
    "OverallFeedbackRequest",
    "OverallFeedbackResult",
    "OverallFeedbackResponse",
]


class FeedbackRequest(BaseModel):
    """개별 피드백 요청"""

    model_config = ConfigDict(populate_by_name=True)

    resume_id: int = Field(alias="resumeId", gt=0)
    question_id: str = Field(alias="questionId", min_length=1)
    answer: str = Field(min_length=1, max_length=5000)


class FeedbackResult(BaseModel):
    """개별 피드백 결과"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    question_id: str = Field(alias="questionId")
    score: int = Field(ge=1, le=10)
    strengths: list[str]
    improvements: list[str]
    model_answer: str = Field(alias="modelAnswer")


class FeedbackErrorResponse(BaseModel):
    """에러 정보"""

    code: str
    message: str


class FeedbackResponse(BaseModel):
    """개별 피드백 응답"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    status: Literal["success", "failed"]
    feedback: FeedbackResult | None = None
    error: FeedbackErrorResponse | None = None


class OverallAnswerItem(BaseModel):
    """종합 피드백 요청 - 개별 답변 항목"""

    model_config = ConfigDict(populate_by_name=True)

    question_id: str = Field(alias="questionId", min_length=1)
    answer: str = Field(min_length=1, max_length=5000)


class OverallFeedbackRequest(BaseModel):
    """종합 피드백 요청"""

    model_config = ConfigDict(populate_by_name=True)

    resume_id: int = Field(alias="resumeId", gt=0)
    answers: list[OverallAnswerItem] = Field(min_length=1)


class OverallFeedbackResult(BaseModel):
    """종합 피드백 결과"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    overall_score: int = Field(alias="overallScore", ge=1, le=10)
    summary: str
    key_strengths: list[str] = Field(alias="keyStrengths")
    key_improvements: list[str] = Field(alias="keyImprovements")


class OverallFeedbackResponse(BaseModel):
    """종합 피드백 응답"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    status: Literal["success", "failed"]
    feedback: OverallFeedbackResult | None = None
    error: FeedbackErrorResponse | None = None
