import asyncio
import uuid
from asyncio import create_task

import httpx
from fastapi import APIRouter

from app.api.utils import send_callback_with_retry
from app.api.v2.schemas.resume_edit import (
    EditCallbackContentData,
    EditCallbackErrorData,
    EditCallbackFailurePayload,
    EditCallbackProjectData,
    EditCallbackSuccessPayload,
    EditRequest,
    EditResponse,
)
from app.api.v2.utils import build_resume_json
from app.core.config import settings
from app.core.context import set_job_id
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.resume.edit_agent import run_edit_agent

router = APIRouter(prefix="/resume", tags=["v2"])
logger = get_logger(__name__)

_background_tasks: set[asyncio.Task] = set()
_tasks_lock = asyncio.Lock()


async def _remove_task(task: asyncio.Task) -> None:
    async with _tasks_lock:
        _background_tasks.discard(task)


def _build_callback_url(job_id: str) -> str:
    """콜백 URL 생성 - /api/resume/{jobId}/callback 형태"""
    base = settings.edit_callback_url.rstrip("/")
    return f"{base}/{job_id}/callback"


def _build_callback_payload(
    job_id: str,
    edited_resume,
    error_message: str | None,
    error_code: ErrorCode | None = None,
) -> dict:
    """콜백 페이로드 생성"""
    if edited_resume:
        payload = EditCallbackSuccessPayload(
            job_id=job_id,
            content=EditCallbackContentData(
                projects=[
                    EditCallbackProjectData(
                        name=p.name,
                        repo_url=p.repo_url,
                        tech_stack=p.tech_stack,
                        description=p.description,
                    )
                    for p in edited_resume.projects
                ],
            ),
            message=getattr(edited_resume, "message", None),
        )
    else:
        payload = EditCallbackFailurePayload(
            job_id=job_id,
            error=EditCallbackErrorData(
                code=error_code or ErrorCode.EDIT_FAILED,
                message=error_message or "이력서 수정에 실패했습니다",
            ),
        )
    return payload.model_dump(by_alias=True)


async def _run_edit_and_callback(
    job_id: str,
    resume_json: str,
    message: str,
) -> None:
    """수정 에이전트 실행 후 콜백 전송"""
    set_job_id(job_id)
    callback_url = _build_callback_url(job_id)

    try:
        edited_resume, error_message, error_code = await run_edit_agent(
            resume_json=resume_json,
            message=message,
            session_id=job_id,
        )

        payload = _build_callback_payload(job_id, edited_resume, error_message, error_code)
        logger.info("콜백 전송 시작", callback_url=callback_url)

        async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
            await send_callback_with_retry(client, callback_url, payload, job_id)

    except Exception as e:
        logger.error("이력서 수정 작업 실패", error=str(e), exc_info=True)
        try:
            payload = _build_callback_payload(job_id, None, "알 수 없는 오류가 발생했습니다")
            async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
                await send_callback_with_retry(client, callback_url, payload, job_id)
        except Exception as cb_err:
            logger.error("실패 콜백 전송도 실패", error=str(cb_err), exc_info=True)


@router.post("/edit", response_model=EditResponse, summary="이력서 수정")
async def edit_resume(
    body: EditRequest,
) -> EditResponse:
    """이력서 수정 요청"""
    job_id = str(uuid.uuid4())
    logger.info(
        "이력서 수정 요청",
        resume_id=body.resume_id,
        job_id=job_id,
    )

    resume_json = build_resume_json(body.content)

    task = create_task(_run_edit_and_callback(job_id, resume_json, body.request_message))
    async with _tasks_lock:
        _background_tasks.add(task)
    task.add_done_callback(lambda t: create_task(_remove_task(t)))

    return EditResponse(job_id=job_id)


def get_background_tasks() -> set[asyncio.Task]:
    """진행 중인 백그라운드 태스크 스냅샷 반환"""
    return set(_background_tasks)
