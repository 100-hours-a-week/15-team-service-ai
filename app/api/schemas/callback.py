from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BaseCallbackProjectData(BaseModel):
    """공통 콜백 프로젝트 데이터"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    name: str
    repo_url: str = Field(alias="repoUrl")
    tech_stack: list[str] = Field(alias="techStack")
    description: str


class BaseCallbackErrorData(BaseModel):
    """공통 콜백 에러 데이터"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    code: str
    message: str


class BaseCallbackFailurePayload(BaseModel):
    """공통 콜백 실패 페이로드"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    job_id: str = Field(alias="jobId")
    status: Literal["failed"] = "failed"
    error: BaseCallbackErrorData
