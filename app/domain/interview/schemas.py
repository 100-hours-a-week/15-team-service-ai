from typing import Literal, TypedDict

from pydantic import BaseModel

__all__ = [
    "InterviewQuestion",
    "InterviewQuestionsOutput",
    "InterviewEvaluationOutput",
    "InterviewState",
]


class InterviewQuestion(BaseModel):
    """면접 질문"""

    question: str
    intent: str
    related_project: str | None = None


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
    session_id: str | None
    questions: InterviewQuestionsOutput
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str
