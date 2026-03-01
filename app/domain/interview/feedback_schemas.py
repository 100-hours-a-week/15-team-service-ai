from typing import TypedDict

from pydantic import BaseModel, Field


class FeedbackOutput(BaseModel):
    """LLM 구조화 출력 - 개별 피드백"""

    score: int = Field(ge=1, le=10)
    strengths: list[str]
    improvements: list[str]
    model_answer: str


class OverallFeedbackOutput(BaseModel):
    """LLM 구조화 출력 - 종합 피드백"""

    overall_score: int = Field(ge=1, le=10)
    summary: str
    key_strengths: list[str]
    key_improvements: list[str]


class OverallFeedbackState(TypedDict, total=False):
    """종합 피드백 LangGraph 워크플로우 상태"""

    position: str
    interview_type: str
    qa_pairs_json: str
    session_id: str | None
    feedback_result: OverallFeedbackOutput
    retry_count: int
    error_code: str
    error_message: str
