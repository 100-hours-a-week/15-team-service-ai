"""이력서 수정 API 스키마"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class EditProjectOutput(BaseModel):
    """LLM 구조화 출력 프로젝트"""

    name: str
    repo_url: str
    tech_stack: list[str]
    description: str


class EditResumeOutput(BaseModel):
    """LLM 구조화 출력 전체"""

    projects: list[EditProjectOutput]


class EditProjectResponse(BaseModel):
    """수정 응답 프로젝트"""

    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    name: str
    repo_url: str = Field(alias="repoUrl")
    tech_stack: list[str] = Field(alias="techStack")
    description: str


class EditContentResponse(BaseModel):
    """수정 응답 이력서 내용"""

    projects: list[EditProjectResponse]


class EditErrorResponse(BaseModel):
    """에러 정보"""

    code: str
    message: str


class EditResponse(BaseModel):
    """이력서 수정 최상위 응답"""

    status: str
    content: EditContentResponse | None = None
    error: EditErrorResponse | None = None
