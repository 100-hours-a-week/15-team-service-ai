import uuid
from asyncio import create_task

from fastapi import APIRouter

from app.api.v1.schemas import GenerateRequest, GenerateResponse
from app.core.config import settings
from app.domain.resume.schemas import ResumeRequest
from app.domain.resume.workflow import create_workflow


router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_resume(request: GenerateRequest) -> GenerateResponse:
    job_id = str(uuid.uuid4())

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

    workflow = create_workflow()
    create_task(workflow.ainvoke(initial_state))

    return GenerateResponse(job_id=job_id)
