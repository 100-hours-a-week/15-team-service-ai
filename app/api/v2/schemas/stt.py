from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TranscriptionRequest(BaseModel):
    """음성 변환 요청"""

    model_config = ConfigDict(populate_by_name=True)

    s3_key: str = Field(alias="s3Key", min_length=1)
    language: str = "ko"


class STTErrorResponse(BaseModel):
    """에러 정보"""

    code: str
    message: str


class TranscriptionResponse(BaseModel):
    """음성 변환 응답"""

    status: Literal["success", "failed"]
    text: str | None = None
    error: STTErrorResponse | None = None
