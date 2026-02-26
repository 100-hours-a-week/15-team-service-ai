from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CallbackProjectData(BaseModel):
    """콜백 프로젝트 데이터"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    name: str
    repo_url: str = Field(alias="repoUrl")
    description: str
    tech_stack: list[str] = Field(alias="techStack")


class CallbackResumeData(BaseModel):
    """콜백 이력서 데이터"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    projects: list[CallbackProjectData]


class CallbackErrorData(BaseModel):
    """콜백 에러 데이터"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    code: str
    message: str


class CallbackSuccessPayload(BaseModel):
    """콜백 성공 페이로드"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    job_id: str = Field(alias="jobId")
    status: Literal["success"] = "success"
    resume: CallbackResumeData


class CallbackFailurePayload(BaseModel):
    """콜백 실패 페이로드"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    job_id: str = Field(alias="jobId")
    status: Literal["failed"] = "failed"
    error: CallbackErrorData
