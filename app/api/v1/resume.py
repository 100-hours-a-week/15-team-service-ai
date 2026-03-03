import asyncio
import uuid
from asyncio import Semaphore, create_task

import httpx
from fastapi import APIRouter, Request

from app.api.utils import send_callback_with_retry
from app.api.v1.schemas import GenerateRequest, GenerateResponse, MockGenerateRequest
from app.api.v1.schemas.callback import (
    CallbackErrorData,
    CallbackFailurePayload,
    CallbackProjectData,
    CallbackResumeData,
    CallbackSuccessPayload,
)
from app.core.config import settings
from app.core.context import github_mock_var, set_job_id
from app.core.exceptions import ErrorCode
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.domain.resume.agent import run_resume_agent
from app.domain.resume.schemas import ResumeData, ResumeRequest

router = APIRouter(prefix="/resume", tags=["v1"])
logger = get_logger(__name__)

MAX_CONCURRENT_JOBS = 10
_job_semaphore = Semaphore(MAX_CONCURRENT_JOBS)
_background_tasks: set[asyncio.Task] = set()


async def _run_agent_and_callback(
    job_id: str,
    request: ResumeRequest,
    callback_url: str,
) -> None:
    """에이전트 실행 후 콜백 전송"""
    set_job_id(job_id)
    async with _job_semaphore:
        logger.info("작업 시작", concurrent_limit=MAX_CONCURRENT_JOBS)
        try:
            resume_data, error_message = await run_resume_agent(
                request=request,
                session_id=job_id,
            )

            payload = _build_callback_payload(job_id, resume_data, error_message)
            logger.info("콜백 전송 시작")

            async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
                await send_callback_with_retry(client, callback_url, payload, job_id)

        except Exception as e:
            logger.error("작업 처리 실패", error=str(e), exc_info=True)
            try:
                payload = _build_callback_payload(job_id, None, "알 수 없는 오류가 발생했습니다")
                async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
                    await send_callback_with_retry(client, callback_url, payload, job_id)
            except Exception as cb_err:
                logger.error("실패 콜백 전송도 실패", error=str(cb_err), exc_info=True)


def _build_callback_payload(
    job_id: str,
    resume_data: ResumeData | None,
    error_message: str | None,
) -> dict:
    """콜백 페이로드 생성"""
    if resume_data:
        payload = CallbackSuccessPayload(
            job_id=job_id,
            resume=CallbackResumeData(
                projects=[
                    CallbackProjectData(
                        name=p.name,
                        repo_url=p.repo_url,
                        description=p.description,
                        tech_stack=p.tech_stack,
                    )
                    for p in resume_data.projects
                ],
            ),
        )
    else:
        payload = CallbackFailurePayload(
            job_id=job_id,
            error=CallbackErrorData(
                code=ErrorCode.GENERATION_FAILED,
                message=error_message or "이력서 생성에 실패했습니다.",
            ),
        )
    return payload.model_dump(by_alias=True)


@router.post("/generate", response_model=GenerateResponse, summary="이력서 생성")
@limiter.limit("5/minute")
async def generate_resume(
    request: Request,
    body: GenerateRequest,
) -> GenerateResponse:
    """이력서 생성 요청

    분당 5회 요청 제한이 적용됩니다
    """
    job_id = str(uuid.uuid4())
    callback_url = settings.generate_callback_url

    resume_request = ResumeRequest(
        repo_urls=body.repo_urls,
        position=body.position,
        company=body.company,
        github_token=body.github_token,
        callback_url=callback_url,
    )

    task = create_task(_run_agent_and_callback(job_id, resume_request, callback_url))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return GenerateResponse(job_id=job_id)


@router.post("/generate/mock", response_model=GenerateResponse, summary="이력서 생성 Mock")
async def generate_resume_mock(
    request: Request,
    body: MockGenerateRequest,
) -> GenerateResponse:
    """GitHub API 없이 모의 데이터로 이력서 생성"""
    
    job_id = str(uuid.uuid4())
    callback_url = settings.generate_callback_url_test

    github_mock_var.set(True)

    resume_request = ResumeRequest(
        repo_urls=body.repo_urls,
        position=body.position,
        company=body.company,
        github_token="mock-token",
        callback_url=callback_url,
    )

    task = create_task(_run_agent_and_callback(job_id, resume_request, callback_url))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return GenerateResponse(job_id=job_id)


def get_background_tasks() -> set[asyncio.Task]:
    """진행 중인 백그라운드 태스크 반환"""
    return _background_tasks
