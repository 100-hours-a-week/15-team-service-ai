"""이력서 생성 Plan 스키마 - Gemini가 프로젝트별로 생성하는 불릿 작성 계획"""

from pydantic import BaseModel, Field


class BulletPlan(BaseModel):
    """개별 불릿 작성 계획"""

    source_commits: list[str] = Field(description="이 불릿의 근거가 되는 커밋/PR 메시지 목록")
    suggested_content: str = Field(description="제안하는 불릿 내용")
    technical_detail: str = Field(description="의존성/PR body에서 추출한 기술 컨텍스트")


class ProjectPlan(BaseModel):
    """프로젝트별 이력서 생성 계획"""

    project_name: str = Field(description="프로젝트 이름")
    repo_url: str = Field(description="GitHub 레포지토리 URL")
    recommended_tech_stack: list[str] = Field(description="추천 기술 스택 5-8개")
    bullet_plans: list[BulletPlan] = Field(description="불릿 작성 계획 5-8개")
    skipped_commits: list[str] = Field(description="불릿에 포함하지 않은 커밋과 사유")
