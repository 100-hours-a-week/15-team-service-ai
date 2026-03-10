from typing import Literal, TypedDict

from pydantic import BaseModel

__all__ = [
    "BEHAVIORAL_DIMENSIONS",
    "InterviewQuestion",
    "InterviewQuestionsOutput",
    "InterviewEvaluationOutput",
    "InterviewState",
]

BEHAVIORAL_DIMENSIONS = Literal[
    "협업",
    "갈등해결",
    "성장마인드",
    "실패경험",
    "우선순위",
    "사용자관점",
    "자기소개",
    "장단점",
    "기타",
]


class InterviewQuestion(BaseModel):
    """면접 질문"""

    question: str
    intent: str
    related_project: str | None = None
    dimension: BEHAVIORAL_DIMENSIONS | None = None
    category: str | None = None


class InterviewQuestionsOutput(BaseModel):
    """LLM 구조화 출력 - 면접 질문 목록"""

    questions: list[InterviewQuestion]


class InterviewEvaluationOutput(BaseModel):
    """면접 질문 평가 출력"""

    result: Literal["pass", "fail"]
    violated_rule: int | None = None
    violated_item: str | None = None
    feedback: str


class InterviewState(TypedDict, total=False):
    """면접 질문 생성 LangGraph 워크플로우 상태"""

    resume_json: str
    interview_type: str
    position: str
    question_count: int
    min_question_count: int
    session_id: str | None
    questions: InterviewQuestionsOutput
    retry_count: int
    error_code: str
    error_message: str
    missing_dimensions: list[str]
    duplicate_categories: list[str]
    invalid_categories: list[str]
    validation_passed: bool
