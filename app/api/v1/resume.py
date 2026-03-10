import asyncio
import uuid
from asyncio import Semaphore, create_task

import httpx
from fastapi import APIRouter

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
from app.core.logging import get_logger
from app.domain.resume.agent import run_resume_agent
from app.domain.resume.schemas import ResumeData, ResumeRequest

router = APIRouter(prefix="/resume", tags=["v1"])
logger = get_logger(__name__)

MAX_CONCURRENT_JOBS = 10
_job_semaphore = Semaphore(MAX_CONCURRENT_JOBS)
_background_tasks: set[asyncio.Task] = set()
_tasks_lock = asyncio.Lock()


async def _remove_task(task: asyncio.Task) -> None:
    async with _tasks_lock:
        _background_tasks.discard(task)


async def _send_callback(
    callback_url: str,
    payload: dict,
    job_id: str,
) -> None:
    """콜백 전송 - 실패 시 로그만 남김"""
    try:
        async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
            await send_callback_with_retry(client, callback_url, payload, job_id)
    except Exception as cb_err:
        logger.error("콜백 전송 실패", error=str(cb_err), exc_info=True)


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
        except Exception as e:
            logger.error("작업 처리 실패", error=str(e), exc_info=True)
            payload = _build_callback_payload(job_id, None, "알 수 없는 오류가 발생했습니다")

        logger.info("콜백 전송 시작")
        await _send_callback(callback_url, payload, job_id)


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
async def generate_resume(
    body: GenerateRequest,
) -> GenerateResponse:
    """이력서 생성 요청"""
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
    async with _tasks_lock:
        _background_tasks.add(task)
    task.add_done_callback(lambda t: create_task(_remove_task(t)))

    return GenerateResponse(job_id=job_id)


@router.post("/generate/mock", response_model=GenerateResponse, summary="이력서 생성 Mock")
async def generate_resume_mock(
    body: MockGenerateRequest,
) -> GenerateResponse:
    """GitHub API 없이 모의 데이터로 이력서 생성"""

    job_id = str(uuid.uuid4())
    callback_url = settings.generate_callback_url

    github_mock_var.set(True)

    resume_request = ResumeRequest(
        repo_urls=body.repo_urls,
        position=body.position,
        company=body.company,
        github_token="mock-token",
        callback_url=callback_url,
    )

    task = create_task(_run_agent_and_callback(job_id, resume_request, callback_url))
    async with _tasks_lock:
        _background_tasks.add(task)
    task.add_done_callback(lambda t: create_task(_remove_task(t)))

    return GenerateResponse(job_id=job_id)


def get_background_tasks() -> set[asyncio.Task]:
    """진행 중인 백그라운드 태스크 스냅샷 반환"""
    return set(_background_tasks)
