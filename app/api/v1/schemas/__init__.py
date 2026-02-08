"""V1 API 스키마"""

from app.api.v1.schemas.callback import (
    CallbackErrorData,
    CallbackFailurePayload,
    CallbackProjectData,
    CallbackResumeData,
    CallbackSuccessPayload,
)
from app.api.v1.schemas.resume import GenerateRequest, GenerateResponse

__all__ = [
    "GenerateRequest",
    "GenerateResponse",
    "CallbackProjectData",
    "CallbackResumeData",
    "CallbackErrorData",
    "CallbackSuccessPayload",
    "CallbackFailurePayload",
]
