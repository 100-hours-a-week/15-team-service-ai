import json
import uuid

from fastapi import APIRouter, Request

from app.api.v2.schemas.feedback import (
    FeedbackErrorResponse,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackResult,
    OverallFeedbackRequest,
    OverallFeedbackResponse,
    OverallFeedbackResult,
)
from app.core.exceptions import ErrorCode
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.domain.interview.feedback_agent import (
    run_feedback_agent,
    run_overall_feedback_agent,
)
from app.domain.interview.store import interview_context_store

router = APIRouter(prefix="/interview", tags=["v2"])
logger = get_logger(__name__)


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="면접 피드백 생성",
)
@limiter.limit("20/minute")
async def create_feedback(
    request: Request,
    body: FeedbackRequest,
) -> FeedbackResponse:
    """개별 면접 질문에 대한 피드백 생성

    분당 20회 요청 제한이 적용됩니다
    """
    session_id = str(uuid.uuid4())
    logger.info(
        "피드백 생성 요청",
        resume_id=body.resume_id,
        question_id=body.question_id,
        session_id=session_id,
    )

    contexts = interview_context_store.get(body.resume_id)
    if not contexts:
        return FeedbackResponse(
            status="failed",
            error=FeedbackErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message="면접 세션이 만료되었습니다",
            ),
        )

    question_ctx = contexts.get(body.question_id)
    if not question_ctx:
        return FeedbackResponse(
            status="failed",
            error=FeedbackErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message="해당 질문을 찾을 수 없습니다",
            ),
        )

    meta = interview_context_store.get_session_meta(body.resume_id)
    if not meta:
        return FeedbackResponse(
            status="failed",
            error=FeedbackErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message="면접 세션 메타데이터가 만료되었습니다",
            ),
        )

    feedback_result, error_message = await run_feedback_agent(
        resume_json=meta.resume_json,
        position=meta.position,
        interview_type=meta.interview_type,
        question_text=question_ctx.question_text,
        question_intent=question_ctx.intent,
        related_project=question_ctx.related_project,
        answer=body.answer,
        session_id=session_id,
    )

    if error_message or not feedback_result:
        logger.error("피드백 생성 실패", error=error_message)
        return FeedbackResponse(
            status="failed",
            error=FeedbackErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message=error_message or "피드백 생성에 실패했습니다",
            ),
        )

    logger.info("피드백 생성 성공", score=feedback_result.score)
    return FeedbackResponse(
        status="success",
        feedback=FeedbackResult(
            question_id=body.question_id,
            score=feedback_result.score,
            strengths=feedback_result.strengths,
            improvements=feedback_result.improvements,
            model_answer=feedback_result.model_answer,
        ),
    )


@router.post(
    "/feedback/overall",
    response_model=OverallFeedbackResponse,
    summary="종합 면접 피드백 생성",
)
@limiter.limit("10/minute")
async def create_overall_feedback(
    request: Request,
    body: OverallFeedbackRequest,
) -> OverallFeedbackResponse:
    """전체 면접에 대한 종합 피드백 생성

    분당 10회 요청 제한이 적용됩니다
    """
    session_id = str(uuid.uuid4())
    logger.info(
        "종합 피드백 생성 요청",
        resume_id=body.resume_id,
        answer_count=len(body.answers),
        session_id=session_id,
    )

    contexts = interview_context_store.get(body.resume_id)
    if not contexts:
        return OverallFeedbackResponse(
            status="failed",
            error=FeedbackErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message="면접 세션이 만료되었습니다",
            ),
        )

    meta = interview_context_store.get_session_meta(body.resume_id)
    if not meta:
        return OverallFeedbackResponse(
            status="failed",
            error=FeedbackErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message="면접 세션 메타데이터가 만료되었습니다",
            ),
        )

    qa_pairs = []
    for item in body.answers:
        question_ctx = contexts.get(item.question_id)
        if not question_ctx:
            return OverallFeedbackResponse(
                status="failed",
                error=FeedbackErrorResponse(
                    code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                    message=f"질문 {item.question_id}을 찾을 수 없습니다",
                ),
            )
        qa_pairs.append(
            {
                "question": question_ctx.question_text,
                "intent": question_ctx.intent,
                "related_project": question_ctx.related_project,
                "answer": item.answer,
            }
        )

    qa_pairs_json = json.dumps(qa_pairs, ensure_ascii=False, indent=2)

    feedback_result, error_message = await run_overall_feedback_agent(
        resume_json=meta.resume_json,
        position=meta.position,
        interview_type=meta.interview_type,
        qa_pairs_json=qa_pairs_json,
        session_id=session_id,
    )

    if error_message or not feedback_result:
        logger.error("종합 피드백 생성 실패", error=error_message)
        return OverallFeedbackResponse(
            status="failed",
            error=FeedbackErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message=error_message or "종합 피드백 생성에 실패했습니다",
            ),
        )

    logger.info(
        "종합 피드백 생성 성공",
        overall_score=feedback_result.overall_score,
    )
    return OverallFeedbackResponse(
        status="success",
        feedback=OverallFeedbackResult(
            overall_score=feedback_result.overall_score,
            summary=feedback_result.summary,
            key_strengths=feedback_result.key_strengths,
            key_improvements=feedback_result.key_improvements,
        ),
    )
