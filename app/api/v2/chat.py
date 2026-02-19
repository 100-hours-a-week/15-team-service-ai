import uuid

from fastapi import APIRouter, Request

from app.api.v2.schemas.chat import (
    ChatErrorResponse,
    ChatRequest,
    ChatResponse,
)
from app.core.exceptions import ErrorCode
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.domain.interview.chat_agent import run_chat_agent
from app.domain.interview.store import interview_context_store

router = APIRouter(prefix="/interview", tags=["v2"])
logger = get_logger(__name__)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="면접 채팅",
)
@limiter.limit("20/minute")
async def chat_interview(
    request: Request,
    body: ChatRequest,
) -> ChatResponse:
    """면접 질문에 대한 실시간 채팅 응답

    분당 20회 요청 제한이 적용됩니다
    """
    session_id = str(uuid.uuid4())
    logger.info(
        "채팅 요청",
        resume_id=body.resume_id,
        question_id=body.question_id,
        session_id=session_id,
    )

    contexts = interview_context_store.get(body.resume_id)
    if not contexts:
        return ChatResponse(
            status="failed",
            error=ChatErrorResponse(
                code=ErrorCode.CHAT_GENERATE_ERROR,
                message="면접 세션이 만료되었습니다",
            ),
        )

    question_ctx = contexts.get(body.question_id)
    if not question_ctx:
        return ChatResponse(
            status="failed",
            error=ChatErrorResponse(
                code=ErrorCode.CHAT_GENERATE_ERROR,
                message="해당 질문을 찾을 수 없습니다",
            ),
        )

    meta = interview_context_store.get_session_meta(body.resume_id)
    if not meta:
        return ChatResponse(
            status="failed",
            error=ChatErrorResponse(
                code=ErrorCode.CHAT_GENERATE_ERROR,
                message="면접 세션 메타데이터가 만료되었습니다",
            ),
        )

    chat_result, error_message = await run_chat_agent(
        resume_json=meta.resume_json,
        position=meta.position,
        interview_type=meta.interview_type,
        question_text=question_ctx.question_text,
        question_intent=question_ctx.intent,
        related_project=question_ctx.related_project,
        answer=body.answer,
        session_id=session_id,
    )

    if error_message or not chat_result:
        logger.error("채팅 응답 실패", error=error_message)
        return ChatResponse(
            status="failed",
            error=ChatErrorResponse(
                code=ErrorCode.CHAT_GENERATE_ERROR,
                message=error_message or "채팅 응답 생성에 실패했습니다",
            ),
        )

    logger.info("채팅 응답 성공")
    return ChatResponse(
        status="success",
        message=chat_result.message,
        follow_up_question=chat_result.follow_up_question,
    )
