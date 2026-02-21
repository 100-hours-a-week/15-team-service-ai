import asyncio
import uuid
from asyncio import create_task

import httpx
from fastapi import APIRouter, Request

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
from app.core.exceptions import ErrorCode
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.domain.resume.edit_agent import run_edit_agent

router = APIRouter(prefix="/resume", tags=["v2"])
logger = get_logger(__name__)

_background_tasks: set[asyncio.Task] = set()


async def _send_callback_with_retry(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    job_id: str,
) -> bool:
    """콜백 전송, 실패 시 지수 백오프로 재시도"""
    max_retries = settings.callback_max_retries
    base_delay = settings.callback_retry_base_delay

    for attempt in range(max_retries):
        try:
            headers = {"X-AI-Callback-Secret": settings.ai_callback_secret}
            response = await client.post(url, json=payload, headers=headers)

            if 200 <= response.status_code < 300:
                logger.info(
                    "콜백 전송 성공",
                    status_code=response.status_code,
                    attempt=attempt + 1,
                )
                return True

            logger.warning(
                "콜백 응답 오류",
                status_code=response.status_code,
                attempt=attempt + 1,
            )

        except httpx.RequestError as e:
            logger.warning(
                "콜백 요청 실패",
                error=type(e).__name__,
                attempt=attempt + 1,
            )

        if attempt < max_retries - 1:
            delay = base_delay * (2**attempt)
            logger.info("콜백 재시도 대기", delay_seconds=delay)
            await asyncio.sleep(delay)

    logger.error("콜백 전송 최종 실패", max_retries=max_retries)
    return False


def _build_callback_url(job_id: str) -> str:
    """콜백 URL 생성 - /api/resume/{jobId}/callback 형태"""
    base = settings.edit_callback_base_url.rstrip("/")
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
            await _send_callback_with_retry(client, callback_url, payload, job_id)

    except Exception as e:
        logger.error("이력서 수정 작업 실패", error=str(e), exc_info=True)
        try:
            payload = _build_callback_payload(job_id, None, "알 수 없는 오류가 발생했습니다")
            async with httpx.AsyncClient(timeout=settings.callback_timeout) as client:
                await _send_callback_with_retry(client, callback_url, payload, job_id)
        except Exception as cb_err:
            logger.error("실패 콜백 전송도 실패", error=str(cb_err), exc_info=True)


@router.post("/edit", response_model=EditResponse, summary="이력서 수정")
@limiter.limit("10/minute")
async def edit_resume(
    request: Request,
    body: EditRequest,
) -> EditResponse:
    """이력서 수정 요청

    분당 10회 요청 제한이 적용됩니다
    """
    job_id = str(uuid.uuid4())
    logger.info(
        "이력서 수정 요청",
        resume_id=body.resume_id,
        job_id=job_id,
    )

    resume_json = build_resume_json(body.content)

    task = create_task(_run_edit_and_callback(job_id, resume_json, body.request_message))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return EditResponse(job_id=job_id)


def get_background_tasks() -> set[asyncio.Task]:
    """진행 중인 백그라운드 태스크 반환"""
    return _background_tasks
