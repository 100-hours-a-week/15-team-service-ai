from typing import Literal, TypedDict

from pydantic import BaseModel

class EditPlanOutput(BaseModel):
    """Gemini 플래너 노드 출력 - 수정 계획"""

    edit_type: Literal["typo_fix", "add", "remove", "replace", "rewrite"]
    target_summary: str
    detailed_instructions: str


class EditProjectOutput(BaseModel):
    """LLM 구조화 출력 프로젝트"""

    name: str
    repo_url: str
    tech_stack: list[str]
    description: str


class EditResumeOutput(BaseModel):
    """LLM 구조화 출력 전체"""

    projects: list[EditProjectOutput]


class EditState(TypedDict, total=False):
    """이력서 수정 LangGraph 워크플로우 상태"""

    resume_json: str
    message: str
    session_id: str | None
    edit_plan: EditPlanOutput
    edited_resume: EditResumeOutput
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str
