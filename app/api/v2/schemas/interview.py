from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "InterviewProjectRequest",
    "InterviewResumeRequest",
    "InterviewRequest",
    "InterviewQuestionResponse",
    "InterviewContentResponse",
    "InterviewErrorResponse",
    "InterviewResponse",
]


class InterviewProjectRequest(BaseModel):
    """면접 요청 프로젝트"""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=200)
    repo_url: str = Field(alias="repoUrl")
    tech_stack: list[str] = Field(alias="techStack", min_length=1)
    description: str = Field(min_length=1)


class InterviewResumeRequest(BaseModel):
    """면접 요청 이력서 내용"""

    projects: list[InterviewProjectRequest] = Field(min_length=1)


class InterviewRequest(BaseModel):
    """면접 질문 생성 최상위 요청"""

    model_config = ConfigDict(populate_by_name=True)

    resume_id: int = Field(alias="resumeId", gt=0)
    content: InterviewResumeRequest
    type: Literal["technical", "behavioral"]
    position: str = Field(min_length=1, max_length=100)


class InterviewQuestionResponse(BaseModel):
    """면접 응답 질문"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    question: str
    intent: str
    related_project: str | None = Field(default=None, alias="relatedProject")


class InterviewContentResponse(BaseModel):
    """면접 응답 내용"""

    questions: list[InterviewQuestionResponse]


class InterviewErrorResponse(BaseModel):
    """에러 정보"""

    code: str
    message: str


class InterviewResponse(BaseModel):
    """면접 질문 생성 최상위 응답"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    status: str
    interview_type: str = Field(alias="interviewType")
    content: InterviewContentResponse | None = None
    error: InterviewErrorResponse | None = None
