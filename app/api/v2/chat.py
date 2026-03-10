from fastapi import APIRouter, Request

from app.api.v2.schemas.chat import (
    ChatErrorResponse,
    ChatRequest,
    ChatResponse,
)
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.interview.chat_agent import run_chat_agent
from app.domain.interview.chat_schemas import MAX_FOLLOW_UP_TURNS
from app.domain.interview.store import interview_context_store

router = APIRouter(prefix="/interview", tags=["v2"])
logger = get_logger(__name__)

SKIP_PATTERNS = ["모르겠", "잘 모르", "패스", "모릅니다", "생각이 안", "기억이 안"]
SELF_PRESENTATION_PATTERNS = ["자기소개", "장단점", "강점과 약점"]
SOLO_PROJECT_PATTERNS = ["혼자 진행", "혼자 했", "개인 프로젝트", "팀원이 없", "팀원은 없"]


def _filter_follow_up(follow_up, body, question_ctx, turn_count):
    """꼬리질문 필터링 — 성의없는 답변, 자기소개, 솔로 프로젝트, 최대 횟수"""
    if any(p in body.answer for p in SKIP_PATTERNS):
        skip_count = interview_context_store.increment_skip_count(
            body.ai_session_id, body.question_id
        )
        if skip_count >= 2:
            follow_up = None
            logger.info("두 번째 성의없는 답변 - 다음 질문으로 이동", skip_count=skip_count)
        else:
            logger.info("첫 번째 성의없는 답변 - LLM 힌트 유지", skip_count=skip_count)

    if follow_up is not None and any(
        p in question_ctx.question_text for p in SELF_PRESENTATION_PATTERNS
    ):
        follow_up = None
        logger.info(
            "자기소개/장단점 질문 - 꼬리질문 강제 null",
            question=question_ctx.question_text,
        )

    if follow_up is not None and any(p in body.answer for p in SOLO_PROJECT_PATTERNS):
        follow_up = None
        logger.info("솔로 프로젝트 감지 - 꼬리질문 강제 null", answer_snippet=body.answer[:50])

    if turn_count >= MAX_FOLLOW_UP_TURNS:
        follow_up = None
        logger.info("최대 꼬리질문 횟수 도달 - 다음 질문으로 이동", max_turns=MAX_FOLLOW_UP_TURNS)

    return follow_up


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="면접 채팅",
)
async def chat_interview(
    request: Request,
    body: ChatRequest,
) -> ChatResponse:
    """면접 질문에 대한 실시간 채팅 응답

    같은 aiSessionId + questionId로 반복 호출하면 이전 대화를 이어갑니다
    """
    thread_id = f"chat-{body.ai_session_id}-{body.question_id}"
    logger.info(
        "채팅 요청",
        ai_session_id=body.ai_session_id,
        question_id=body.question_id,
        thread_id=thread_id,
    )

    contexts = interview_context_store.get(body.ai_session_id)
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

    meta = interview_context_store.get_session_meta(body.ai_session_id)
    if not meta:
        return ChatResponse(
            status="failed",
            error=ChatErrorResponse(
                code=ErrorCode.CHAT_GENERATE_ERROR,
                message="면접 세션 메타데이터가 만료되었습니다",
            ),
        )

    checkpointer = getattr(request.app.state, "checkpointer", None)

    try:
        chat_result, error_message, turn_count = await run_chat_agent(
            resume_json=meta.resume_json,
            position=meta.position,
            interview_type=meta.interview_type,
            question_text=question_ctx.question_text,
            question_intent=question_ctx.intent,
            related_project=question_ctx.related_project,
            answer=body.answer,
            session_id=body.ai_session_id,
            thread_id=thread_id,
            checkpointer=checkpointer,
        )
    except Exception:
        logger.error("채팅 응답 예외 발생", exc_info=True)
        return ChatResponse(
            status="failed",
            error=ChatErrorResponse(
                code=ErrorCode.CHAT_GENERATE_ERROR,
                message="채팅 응답 생성 중 오류가 발생했습니다",
            ),
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

    follow_up = _filter_follow_up(chat_result.follow_up_question, body, question_ctx, turn_count)

    logger.info("채팅 응답 성공", turn_count=turn_count)
    return ChatResponse(
        status="success",
        message=chat_result.message,
        follow_up_question=follow_up,
        turn_number=turn_count,
    )
