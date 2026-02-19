from typing import Literal, TypedDict

from pydantic import BaseModel


class FeedbackOutput(BaseModel):
    """LLM 구조화 출력 - 개별 피드백"""

    score: int
    strengths: list[str]
    improvements: list[str]
    model_answer: str


class FeedbackEvaluationOutput(BaseModel):
    """개별 피드백 평가 출력"""

    result: Literal["pass", "fail"]
    feedback: str


class OverallFeedbackOutput(BaseModel):
    """LLM 구조화 출력 - 종합 피드백"""

    overall_score: int
    summary: str
    key_strengths: list[str]
    key_improvements: list[str]


class OverallFeedbackEvaluationOutput(BaseModel):
    """종합 피드백 평가 출력"""

    result: Literal["pass", "fail"]
    feedback: str


class FeedbackState(TypedDict, total=False):
    """개별 피드백 LangGraph 워크플로우 상태"""

    resume_json: str
    position: str
    interview_type: str
    question_text: str
    question_intent: str
    related_project: str | None
    answer: str
    session_id: str | None
    feedback_result: FeedbackOutput
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str


class OverallFeedbackState(TypedDict, total=False):
    """종합 피드백 LangGraph 워크플로우 상태"""

    resume_json: str
    position: str
    interview_type: str
    qa_pairs_json: str
    session_id: str | None
    feedback_result: OverallFeedbackOutput
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str
