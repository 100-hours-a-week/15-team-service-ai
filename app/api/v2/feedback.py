import asyncio
import json
import uuid

from fastapi import APIRouter, Request

from app.api.v2.schemas.feedback import (
    InterviewEndErrorResponse,
    InterviewEndFeedbackItem,
    InterviewEndOverallFeedback,
    InterviewEndRequest,
    InterviewEndResponse,
)
from app.core.exceptions import ErrorCode
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.domain.interview.feedback_agent import (
    run_feedback_agent,
    run_overall_feedback_agent,
)

router = APIRouter(prefix="/interview", tags=["v2"])
logger = get_logger(__name__)

MAX_CONCURRENT_FEEDBACK = 5


@router.post(
    "/end",
    response_model=InterviewEndResponse,
    summary="면접 종료 및 피드백 생성",
)
@limiter.limit("10/minute")
async def end_interview(
    request: Request,
    body: InterviewEndRequest,
) -> InterviewEndResponse:
    """면접 종료 시 개별 + 종합 피드백을 한 번에 생성

    분당 10회 요청 제한이 적용됩니다
    """
    session_id = str(uuid.uuid4())
    interview_type = body.interview_type.lower()

    logger.info(
        "면접 종료 피드백 요청",
        ai_session_id=body.ai_session_id,
        interview_type=interview_type,
        position=body.position,
        message_count=len(body.messages),
        session_id=session_id,
    )

    qa_pairs = [{"question": m.question, "answer": m.answer} for m in body.messages]
    qa_pairs_json = json.dumps(qa_pairs, ensure_ascii=False, indent=2)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDBACK)

    async def run_feedback_with_semaphore(m):
        async with semaphore:
            return await run_feedback_agent(
                resume_json="없음",
                position=body.position,
                interview_type=interview_type,
                question_text=m.question,
                question_intent="제공되지 않음",
                related_project=None,
                answer=m.answer,
                session_id=session_id,
            )

    individual_tasks = [run_feedback_with_semaphore(m) for m in body.messages]

    overall_task = run_overall_feedback_agent(
        resume_json="없음",
        position=body.position,
        interview_type=interview_type,
        qa_pairs_json=qa_pairs_json,
        session_id=session_id,
    )

    all_results = await asyncio.gather(*individual_tasks, overall_task, return_exceptions=True)

    individual_results = all_results[:-1]
    feedback_items = []
    individual_errors = []

    for idx, result in enumerate(individual_results):
        msg = body.messages[idx]
        if isinstance(result, Exception):
            logger.error(
                "개별 피드백 생성 실패",
                turn_no=msg.turn_no,
                error=str(result),
                exc_info=result,
            )
            individual_errors.append(f"턴 {msg.turn_no}: 피드백 생성에 실패했습니다")
            continue
        feedback_result, error_message = result
        if error_message or not feedback_result:
            individual_errors.append(f"턴 {msg.turn_no}: {error_message or '생성 실패'}")
            continue
        feedback_items.append(
            InterviewEndFeedbackItem(
                turn_no=msg.turn_no,
                score=feedback_result.score,
                strengths=feedback_result.strengths,
                improvements=feedback_result.improvements,
                model_answer=feedback_result.model_answer,
            )
        )

    overall_entry = all_results[-1]
    overall_feedback = None
    overall_error = None

    if isinstance(overall_entry, Exception):
        logger.error("종합 피드백 생성 실패", error=str(overall_entry), exc_info=overall_entry)
        overall_error = "종합 피드백 생성에 실패했습니다"
    else:
        overall_result, overall_err_msg = overall_entry
        if overall_err_msg or not overall_result:
            overall_error = overall_err_msg or "종합 피드백 생성 실패"
        else:
            overall_feedback = InterviewEndOverallFeedback(
                overall_score=overall_result.overall_score,
                summary=overall_result.summary,
                key_strengths=overall_result.key_strengths,
                key_improvements=overall_result.key_improvements,
            )

    if not feedback_items and not overall_feedback:
        error_msgs = individual_errors + ([overall_error] if overall_error else [])
        logger.error("피드백 전체 실패", errors=error_msgs)
        return InterviewEndResponse(
            status="failed",
            error=InterviewEndErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message="; ".join(error_msgs) or "피드백 생성에 실패했습니다",
            ),
        )

    if individual_errors:
        logger.warning("일부 개별 피드백 실패", errors=individual_errors)

    if overall_error:
        logger.warning("종합 피드백 실패", error=overall_error)

    logger.info(
        "면접 피드백 생성 완료",
        individual_count=len(feedback_items),
        has_overall=overall_feedback is not None,
    )

    return InterviewEndResponse(
        status="success",
        feedbacks=feedback_items if feedback_items else None,
        overall_feedback=overall_feedback,
    )
