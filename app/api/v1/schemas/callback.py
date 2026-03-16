from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.callback import (
    BaseCallbackErrorData,
    BaseCallbackFailurePayload,
    BaseCallbackProjectData,
)

CallbackProjectData = BaseCallbackProjectData
CallbackErrorData = BaseCallbackErrorData
CallbackFailurePayload = BaseCallbackFailurePayload


class CallbackResumeData(BaseModel):
    """콜백 이력서 데이터"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    projects: list[CallbackProjectData]


class CallbackSuccessPayload(BaseModel):
    """콜백 성공 페이로드"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    job_id: str = Field(alias="jobId")
    status: Literal["success"] = "success"
    resume: CallbackResumeData
