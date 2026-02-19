import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interview.feedback_schemas import (
    FeedbackOutput,
    FeedbackState,
    OverallFeedbackOutput,
    OverallFeedbackState,
)
from app.domain.interview.feedback_workflow import (
    create_feedback_workflow,
    create_overall_feedback_workflow,
)
from app.infra.llm.client import get_langfuse_handler

logger = get_logger(__name__)

_feedback_workflow = create_feedback_workflow()
_overall_feedback_workflow = create_overall_feedback_workflow()


async def run_feedback_agent(
    resume_json: str,
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    session_id: str | None = None,
) -> tuple[FeedbackOutput | None, str | None]:
    """개별 피드백 워크플로우 실행

    Returns:
        feedback_result, error_message 튜플
    """
    logger.info("피드백 에이전트 시작", session_id=session_id)

    try:
        initial_state: FeedbackState = {
            "resume_json": resume_json,
            "position": position,
            "interview_type": interview_type,
            "question_text": question_text,
            "question_intent": question_intent,
            "related_project": related_project,
            "answer": answer,
            "session_id": session_id,
            "retry_count": 0,
        }

        langfuse_handler = get_langfuse_handler()
        config = {"callbacks": [langfuse_handler]} if langfuse_handler else {}

        final_state = await asyncio.wait_for(
            _feedback_workflow.ainvoke(initial_state, config=config),
            timeout=settings.workflow_timeout,
        )

        if final_state.get("error_code"):
            error_msg = final_state.get("error_message", "알 수 없는 오류")
            logger.error(
                "피드백 워크플로우 실패",
                error_code=final_state.get("error_code"),
            )
            return None, error_msg

        feedback_result = final_state.get("feedback_result")
        if not feedback_result:
            return None, "피드백 생성 실패"

        logger.info("피드백 에이전트 완료", score=feedback_result.score)
        return feedback_result, None

    except asyncio.TimeoutError:
        logger.error("피드백 워크플로우 타임아웃", timeout=settings.workflow_timeout)
        return None, f"워크플로우 타임아웃: {settings.workflow_timeout}초 초과"

    except Exception as e:
        logger.error("피드백 에이전트 실패", error=str(e), exc_info=True)
        return None, "알 수 없는 오류가 발생했습니다"


async def run_overall_feedback_agent(
    resume_json: str,
    position: str,
    interview_type: str,
    qa_pairs_json: str,
    session_id: str | None = None,
) -> tuple[OverallFeedbackOutput | None, str | None]:
    """종합 피드백 워크플로우 실행

    Returns:
        feedback_result, error_message 튜플
    """
    logger.info("종합 피드백 에이전트 시작", session_id=session_id)

    try:
        initial_state: OverallFeedbackState = {
            "resume_json": resume_json,
            "position": position,
            "interview_type": interview_type,
            "qa_pairs_json": qa_pairs_json,
            "session_id": session_id,
            "retry_count": 0,
        }

        langfuse_handler = get_langfuse_handler()
        config = {"callbacks": [langfuse_handler]} if langfuse_handler else {}

        final_state = await asyncio.wait_for(
            _overall_feedback_workflow.ainvoke(initial_state, config=config),
            timeout=settings.workflow_timeout,
        )

        if final_state.get("error_code"):
            error_msg = final_state.get("error_message", "알 수 없는 오류")
            logger.error(
                "종합 피드백 워크플로우 실패",
                error_code=final_state.get("error_code"),
            )
            return None, error_msg

        feedback_result = final_state.get("feedback_result")
        if not feedback_result:
            return None, "종합 피드백 생성 실패"

        logger.info(
            "종합 피드백 에이전트 완료",
            overall_score=feedback_result.overall_score,
        )
        return feedback_result, None

    except asyncio.TimeoutError:
        logger.error(
            "종합 피드백 워크플로우 타임아웃",
            timeout=settings.workflow_timeout,
        )
        return None, f"워크플로우 타임아웃: {settings.workflow_timeout}초 초과"

    except Exception as e:
        logger.error("종합 피드백 에이전트 실패", error=str(e), exc_info=True)
        return None, "알 수 없는 오류가 발생했습니다"
