import asyncio
import json

from fastapi import APIRouter

from app.api.v2.schemas.feedback import (
    InterviewEndErrorResponse,
    InterviewEndFeedbackItem,
    InterviewEndOverallFeedback,
    InterviewEndRequest,
    InterviewEndResponse,
)
from app.core.config import settings
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.interview.feedback_agent import (
    run_all_feedback_agents,
    run_feedback_agent,
    run_overall_feedback_agent,
)
from app.domain.interview.store import interview_context_store
from app.infra.llm.base import get_langfuse_parent_handler
from app.infra.tavily.client import search_company_talent

router = APIRouter(prefix="/interview", tags=["v2"])
logger = get_logger(__name__)

MAX_CONCURRENT_FEEDBACK = 10
FEEDBACK_GATHER_TIMEOUT = settings.feedback_gather_timeout


def _process_individual_results(
    individual_results: list,
    messages: list,
) -> tuple[list[InterviewEndFeedbackItem], list[str], str]:
    """개별 피드백 결과를 처리하여 피드백 아이템, 에러, JSON 반환"""
    feedback_items: list[InterviewEndFeedbackItem] = []
    individual_errors: list[str] = []
    individual_feedbacks: list[dict] = []

    for idx, result in enumerate(individual_results):
        msg = messages[idx]
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
        individual_feedbacks.append(
            {
                "turn_no": msg.turn_no,
                "score": feedback_result.score,
                "strengths": feedback_result.strengths,
                "improvements": feedback_result.improvements,
            }
        )

    individual_feedbacks_json = json.dumps(individual_feedbacks, ensure_ascii=False)
    return feedback_items, individual_errors, individual_feedbacks_json


async def _generate_overall_feedback(
    position: str,
    interview_type: str,
    qa_pairs_json: str,
    individual_feedbacks_json: str,
    session_id: str,
    company: str = "",
    company_talent_info: str = "",
) -> tuple[InterviewEndOverallFeedback | None, str | None]:
    """종합 피드백 생성 후 응답 스키마로 변환"""
    overall_result, overall_err_msg = await run_overall_feedback_agent(
        position=position,
        interview_type=interview_type,
        qa_pairs_json=qa_pairs_json,
        individual_feedbacks_json=individual_feedbacks_json,
        company=company,
        company_talent_info=company_talent_info,
        session_id=session_id,
    )

    if overall_err_msg or not overall_result:
        logger.error("종합 피드백 생성 실패", error=overall_err_msg)
        return None, overall_err_msg or "종합 피드백 생성 실패"

    return InterviewEndOverallFeedback(
        overall_score=overall_result.overall_score,
        summary=overall_result.summary,
        key_strengths=overall_result.key_strengths,
        key_improvements=overall_result.key_improvements,
    ), None


def _build_feedback_response(
    feedback_items: list[InterviewEndFeedbackItem],
    overall_feedback: InterviewEndOverallFeedback | None,
    individual_errors: list[str],
    overall_error: str | None,
) -> InterviewEndResponse:
    """최종 피드백 응답 빌드"""
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


@router.post(
    "/end",
    response_model=InterviewEndResponse,
    summary="면접 종료 및 피드백 생성",
)
async def end_interview(
    body: InterviewEndRequest,
) -> InterviewEndResponse:
    """면접 종료 시 개별 + 종합 피드백을 한 번에 생성"""
    interview_type = body.interview_type.lower()

    logger.info(
        "면접 종료 피드백 요청",
        ai_session_id=body.ai_session_id,
        interview_type=interview_type,
        position=body.position,
        message_count=len(body.messages),
    )

    qa_pairs = [
        {
            "question": m.question,
            "answer": m.answer,
            "answer_input_type": m.answer_input_type,
        }
        for m in body.messages
    ]
    qa_pairs_json = json.dumps(qa_pairs, ensure_ascii=False, indent=2)

    contexts = interview_context_store.get(body.ai_session_id)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDBACK)
    langfuse_parent = get_langfuse_parent_handler(
        "individual-feedbacks",
        session_id=body.ai_session_id,
    )
    parent_callbacks = [langfuse_parent] if langfuse_parent else None

    async def run_feedback_with_semaphore(m, idx):
        qid = f"q-{idx:03d}"
        ctx = contexts.get(qid) if contexts else None
        async with semaphore:
            return await run_feedback_agent(
                position=body.position,
                interview_type=interview_type,
                question_text=m.question,
                question_intent=ctx.intent if ctx else "",
                related_project=ctx.related_project if ctx else None,
                answer=m.answer,
                session_id=body.ai_session_id,
                callbacks=parent_callbacks,
            )

    individual_tasks = [
        run_feedback_with_semaphore(m, idx) for idx, m in enumerate(body.messages, start=1)
    ]

    talent_search_task = asyncio.create_task(search_company_talent(body.company))

    try:
        individual_results = await asyncio.wait_for(
            run_all_feedback_agents(individual_tasks),
            timeout=FEEDBACK_GATHER_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error(
            "개별 피드백 전체 타임아웃",
            timeout=FEEDBACK_GATHER_TIMEOUT,
        )
        talent_search_task.cancel()
        return InterviewEndResponse(
            status="failed",
            error=InterviewEndErrorResponse(
                code=ErrorCode.FEEDBACK_GENERATE_ERROR,
                message=f"피드백 생성 타임아웃: {FEEDBACK_GATHER_TIMEOUT}초 초과",
            ),
        )

    company_talent_info = await talent_search_task

    feedback_items, individual_errors, individual_feedbacks_json = _process_individual_results(
        individual_results, body.messages
    )

    overall_feedback, overall_error = await _generate_overall_feedback(
        position=body.position,
        interview_type=interview_type,
        qa_pairs_json=qa_pairs_json,
        individual_feedbacks_json=individual_feedbacks_json,
        company=body.company,
        company_talent_info=company_talent_info,
        session_id=body.ai_session_id,
    )

    return _build_feedback_response(
        feedback_items, overall_feedback, individual_errors, overall_error
    )
