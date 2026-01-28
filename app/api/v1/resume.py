import asyncio
import uuid
from asyncio import Semaphore, create_task

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

MAX_CONCURRENT_JOBS = 10
_job_semaphore = Semaphore(MAX_CONCURRENT_JOBS)


async def _send_callback_with_retry(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    job_id: str,
) -> bool:
    """Callback 전송, 실패 시 지수 백오프로 재시도"""
    max_retries = settings.callback_max_retries
    base_delay = settings.callback_retry_base_delay

    for attempt in range(max_retries):
        try:
            response = await client.post(url, json=payload)

            if 200 <= response.status_code < 300:
                logger.info(
                    "콜백 전송 성공 job_id=%s status_code=%d attempt=%d",
                    job_id,
                    response.status_code,
                    attempt + 1,
                )
                return True

            logger.warning(
                "콜백 응답 오류 job_id=%s status_code=%d attempt=%d",
                job_id,
                response.status_code,
                attempt + 1,
            )

        except httpx.RequestError as e:
            logger.warning(
                "콜백 요청 실패 job_id=%s error=%s attempt=%d",
                job_id,
                type(e).__name__,
                attempt + 1,
            )

        if attempt < max_retries - 1:
            delay = base_delay * (2**attempt)
            logger.info("콜백 재시도 대기 job_id=%s delay=%.1f초", job_id, delay)
            await asyncio.sleep(delay)

    logger.error(
        "콜백 전송 최종 실패 job_id=%s max_retries=%d",
        job_id,
        max_retries,
    )
    return False


async def _run_agent_and_callback(
    job_id: str,
    request: ResumeRequest,
    callback_url: str,
) -> None:
    """에이전트 실행 후 콜백 전송"""
    async with _job_semaphore:
        logger.info("작업 시작 job_id=%s 동시작업제한=%d", job_id, MAX_CONCURRENT_JOBS)
        try:
            resume_data, error_message = await run_resume_agent(
                request=request,
                session_id=job_id,
            )

            payload = _build_callback_payload(job_id, resume_data, error_message)
            logger.info("콜백 전송 시작 job_id=%s", job_id)

            async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
                await _send_callback_with_retry(client, callback_url, payload, job_id)

        except Exception as e:
            logger.error("작업 처리 실패 job_id=%s error=%s", job_id, e)


def _build_callback_payload(
    job_id: str,
    resume_data: ResumeData | None,
    error_message: str | None,
) -> dict:
    """콜백 페이로드 생성"""
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
    callback_url = settings.backend_callback_url

    resume_request = ResumeRequest(
        repo_urls=request.repo_urls,
        position=request.position,
        company=request.company,
        github_token=request.github_token,
        callback_url=callback_url,
    )

    create_task(_run_agent_and_callback(job_id, resume_request, callback_url))

    return GenerateResponse(job_id=job_id)
