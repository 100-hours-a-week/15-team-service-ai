"""이력서 수정 워크플로우 상태"""

from typing import TypedDict

from app.api.v2.schemas.resume_edit import EditResumeOutput


class EditState(TypedDict, total=False):
    """이력서 수정 LangGraph 워크플로우 상태"""

    resume_json: str
    message: str
    session_id: str | None
    edited_resume: EditResumeOutput
    evaluation: str
    evaluation_feedback: str
    retry_count: int
    error_code: str
    error_message: str
