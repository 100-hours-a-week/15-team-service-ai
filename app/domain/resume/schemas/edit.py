from typing import Literal, TypedDict

from pydantic import AliasChoices, BaseModel, Field


class ClassifyOutput(BaseModel):
    """Gemini 분류 노드 출력 - 요청 분류"""

    intent_category: Literal["typo_fix", "add", "remove", "replace", "rewrite", "out_of_scope"]
    confidence: Literal["high", "medium", "low"]
    reason: str


class EditPlanOutput(BaseModel):
    """Gemini 플래너 노드 출력 - 수정 계획"""

    edit_type: Literal["typo_fix", "add", "remove", "replace", "rewrite"]
    target_summary: str
    detailed_instructions: str


class EditProjectOutput(BaseModel):
    """LLM 구조화 출력 프로젝트"""

    name: str
    repo_url: str = Field(validation_alias=AliasChoices("repo_url", "repoUrl"))
    tech_stack: list[str] = Field(validation_alias=AliasChoices("tech_stack", "techStack"))
    description: str


class EditResumeOutput(BaseModel):
    """LLM 구조화 출력 전체"""

    projects: list[EditProjectOutput]


class EditState(TypedDict, total=False):
    """이력서 수정 LangGraph 워크플로우 상태"""

    resume_json: str
    message: str
    session_id: str | None
    classification: ClassifyOutput
    reject_reason: str | None
    edit_plan: EditPlanOutput
    edited_resume: EditResumeOutput
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str
