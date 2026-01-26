import uuid
from asyncio import create_task

import httpx
from fastapi import APIRouter

from app.api.v1.schemas import GenerateRequest, GenerateResponse
from app.core.config import settings
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.resume.agent import run_resume_agent
from app.domain.resume.schemas import ResumeData, ResumeRequest

router = APIRouter(prefix="/resume", tags=["resume"])
logger = get_logger(__name__)


async def _run_agent_and_callback(
    job_id: str,
    request: ResumeRequest,
    callback_url: str,
) -> None:
    """에이전트 실행 후 콜백 전송."""
    try:
        resume_data, error_message = await run_resume_agent(
            request=request,
            session_id=job_id,
        )

        payload = _build_callback_payload(job_id, resume_data, error_message)
        logger.info("콜백 전송 시작 job_id=%s url=%s", job_id, callback_url)

        async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
            response = await client.post(callback_url, json=payload)
            logger.info(
                "콜백 전송 완료 job_id=%s status=%s response=%d",
                job_id,
                payload["status"],
                response.status_code,
            )
    except Exception as e:
        logger.error("콜백 전송 실패 job_id=%s error=%s", job_id, e)


def _build_callback_payload(
    job_id: str,
    resume_data: ResumeData | None,
    error_message: str | None,
) -> dict:
    """콜백 페이로드 생성."""
    if resume_data:
        return {
            "jobId": job_id,
            "status": "success",
            "resume": {
                "projects": [
                    {
                        "name": p.name,
                        "repoUrl": p.repo_url,
                        "description": p.description,
                        "techStack": p.tech_stack,
                    }
                    for p in resume_data.projects
                ],
            },
        }
    else:
        return {
            "jobId": job_id,
            "status": "failed",
            "error": {
                "code": ErrorCode.GENERATION_FAILED,
                "message": error_message or "이력서 생성에 실패했습니다.",
            },
        }


@router.post("/generate", response_model=GenerateResponse)
async def generate_resume(request: GenerateRequest) -> GenerateResponse:
    job_id = str(uuid.uuid4())
    callback_url = request.callback_url or settings.backend_callback_url

    resume_request = ResumeRequest(
        repo_urls=request.repo_urls,
        position=request.position,
        company=request.company,
        github_token=request.github_token,
        callback_url=callback_url,
    )

    create_task(_run_agent_and_callback(job_id, resume_request, callback_url))

    return GenerateResponse(job_id=job_id)
