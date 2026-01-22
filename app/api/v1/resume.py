import uuid
from asyncio import create_task

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.resume.schemas import ResumeRequest
from app.domain.resume.workflow import create_workflow


router = APIRouter(prefix="/resume", tags=["resume"])


class GenerateRequest(BaseModel):
    """이력서 생성 요청 (API 스펙)."""

    repo_urls: list[str] = Field(alias="repoUrls")
    position: str
    company: str | None = None
    github_token: str = Field(alias="githubToken")
    callback_url: str | None = Field(default=None, alias="callbackUrl")

    class Config:
        populate_by_name = True


class GenerateResponse(BaseModel):
    """이력서 생성 응답."""

    job_id: str = Field(alias="jobId")

    class Config:
        populate_by_name = True
        by_alias = True


@router.post("/generate", response_model=GenerateResponse)
async def generate_resume(request: GenerateRequest) -> GenerateResponse:
    """이력서 생성 요청.

    jobId를 즉시 반환하고, 백그라운드에서 이력서 생성 후 callbackUrl로 결과 전송.
    """
    job_id = str(uuid.uuid4())

    # callback_url: 요청에 있으면 사용, 없으면 .env 기본값 사용
    callback_url = request.callback_url or settings.backend_callback_url

    # 워크플로우 실행을 위한 상태 생성
    resume_request = ResumeRequest(
        repo_urls=request.repo_urls,
        position=request.position,
        company=request.company,
        github_token=request.github_token,
        callback_url=callback_url,
    )

    initial_state = {
        "request": resume_request,
        "job_id": job_id,
    }

    # 백그라운드에서 워크플로우 실행
    workflow = create_workflow()
    create_task(workflow.ainvoke(initial_state))

    return GenerateResponse(job_id=job_id)
