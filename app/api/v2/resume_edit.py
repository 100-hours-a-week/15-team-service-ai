import json
import uuid

from fastapi import APIRouter, Request

from app.api.v2.schemas.resume_edit import (
    EditContentResponse,
    EditErrorResponse,
    EditProjectResponse,
    EditRequest,
    EditResponse,
)
from app.core.exceptions import ErrorCode
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.domain.resume.edit_agent import run_edit_agent

router = APIRouter(prefix="/resume", tags=["resume-edit"])
logger = get_logger(__name__)


def _build_resume_json(body: EditRequest) -> str:
    """요청 데이터를 LLM 입력용 JSON 문자열로 변환"""
    projects = []
    for p in body.content.projects:
        projects.append(
            {
                "name": p.name,
                "repo_url": p.repo_url,
                "tech_stack": p.tech_stack,
                "description": p.description,
            }
        )
    return json.dumps({"projects": projects}, ensure_ascii=False, indent=2)


@router.post("/edit", response_model=EditResponse)
@limiter.limit("10/minute")
async def edit_resume(
    request: Request,
    body: EditRequest,
) -> EditResponse:
    """이력서 수정 요청

    분당 10회 요청 제한이 적용됩니다
    """
    session_id = str(uuid.uuid4())
    logger.info(
        "이력서 수정 요청",
        resume_id=body.resume_id,
        session_id=session_id,
    )

    resume_json = _build_resume_json(body)

    edited_resume, error_message = await run_edit_agent(
        resume_json=resume_json,
        message=body.request_message,
        session_id=session_id,
    )

    if error_message or not edited_resume:
        logger.error("이력서 수정 실패", error=error_message)
        return EditResponse(
            status="failed",
            error=EditErrorResponse(
                code=ErrorCode.EDIT_FAILED,
                message=error_message or "이력서 수정에 실패했습니다",
            ),
        )

    content = EditContentResponse(
        projects=[
            EditProjectResponse(
                name=p.name,
                repo_url=p.repo_url,
                tech_stack=p.tech_stack,
                description=p.description,
            )
            for p in edited_resume.projects
        ],
    )

    logger.info("이력서 수정 성공", projects=len(edited_resume.projects))
    return EditResponse(status="success", content=content)
