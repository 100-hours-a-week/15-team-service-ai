from typing import Literal, TypedDict

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.domain.resume.schemas.github import RepoContext, UserStats
from app.domain.resume.schemas.plan import ProjectPlan


class ProjectInfoDict(TypedDict):
    """프로젝트 데이터 수집 결과"""

    repo_name: str
    repo_url: str
    file_tree: list[str]
    dependencies: list[str]
    messages: list[str]


class ResumeRequest(BaseModel):
    """이력서 생성 요청"""

    repo_urls: list[str]
    position: str
    company: str | None = None
    github_token: str | None = None
    callback_url: str | None = None


class ProjectInfo(BaseModel):
    """프로젝트 정보"""

    name: str = Field(description="프로젝트 이름")
    repo_url: str = Field(
        description="GitHub 레포지토리 URL",
        validation_alias=AliasChoices("repo_url", "repoUrl"),
    )
    description: str = Field(
        description="불릿 포인트 형식의 프로젝트 설명, 5-8개, "
        "각 줄은 '- '로 시작하고 허용된 어미로 종료"
    )

    @field_validator("description", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v: object) -> str:
        """LLM이 description을 리스트로 출력하는 경우 줄바꿈으로 합쳐서 문자열로 변환"""
        if isinstance(v, list):
            return "\n".join(str(item) for item in v)
        return v

    tech_stack: list[str] = Field(
        description="프로젝트에서 사용한 기술 스택 5-8개, 의존성에서 확인된 기술만 포함",
        validation_alias=AliasChoices("tech_stack", "techStack"),
    )


class ResumeData(BaseModel):
    """생성된 이력서 데이터"""

    projects: list[ProjectInfo]


class EvaluationOutput(BaseModel):
    """이력서 평가 LLM 출력"""

    result: Literal["pass", "fail"]
    violated_rule: int | None = None
    violated_item: str | None = None
    feedback: str


class ResumeState(TypedDict, total=False):
    """LangGraph 워크플로우 상태"""

    request: ResumeRequest
    job_id: str
    session_id: str | None
    project_info: list[ProjectInfoDict]
    repo_contexts: dict[str, RepoContext]
    user_stats: UserStats | None
    project_plans: list[ProjectPlan]
    resume_data: ResumeData
    error_code: str
    error_message: str
