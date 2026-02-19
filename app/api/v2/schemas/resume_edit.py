from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.resume.schemas.edit import EditProjectOutput, EditResumeOutput

__all__ = [
    "EditProjectRequest",
    "EditContentRequest",
    "EditRequest",
    "EditProjectOutput",
    "EditResumeOutput",
    "EditResponse",
    "EditCallbackProjectData",
    "EditCallbackContentData",
    "EditCallbackErrorData",
    "EditCallbackSuccessPayload",
    "EditCallbackFailurePayload",
]


class EditProjectRequest(BaseModel):
    """수정 요청 프로젝트"""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=200)
    repo_url: str = Field(alias="repoUrl")
    tech_stack: list[str] = Field(alias="techStack", min_length=1)
    description: str = Field(min_length=1)


class EditContentRequest(BaseModel):
    """수정 요청 이력서 내용"""

    projects: list[EditProjectRequest] = Field(min_length=1)


class EditRequest(BaseModel):
    """이력서 수정 최상위 요청"""

    model_config = ConfigDict(populate_by_name=True)

    resume_id: int = Field(alias="resumeId", gt=0)
    content: EditContentRequest
    request_message: str = Field(alias="requestMessage", min_length=1, max_length=1000)

    @field_validator("request_message")
    @classmethod
    def validate_request_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("수정 요청 메시지가 비어있습니다")
        return stripped


class EditResponse(BaseModel):
    """이력서 수정 요청 응답 - jobId만 즉시 반환"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    job_id: str = Field(alias="jobId")


class EditCallbackProjectData(BaseModel):
    """콜백 프로젝트 데이터"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    name: str
    repo_url: str = Field(alias="repoUrl")
    tech_stack: list[str] = Field(alias="techStack")
    description: str


class EditCallbackContentData(BaseModel):
    """콜백 이력서 내용 데이터"""

    projects: list[EditCallbackProjectData]


class EditCallbackErrorData(BaseModel):
    """콜백 에러 데이터"""

    code: str
    message: str


class EditCallbackSuccessPayload(BaseModel):
    """콜백 성공 페이로드"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    job_id: str = Field(alias="jobId")
    status: Literal["success"] = "success"
    content: EditCallbackContentData


class EditCallbackFailurePayload(BaseModel):
    """콜백 실패 페이로드"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    job_id: str = Field(alias="jobId")
    status: Literal["failed"] = "failed"
    error: EditCallbackErrorData
