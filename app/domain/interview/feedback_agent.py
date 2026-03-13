import asyncio

from langsmith import traceable

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
from app.infra.llm.base import _build_langfuse_config

logger = get_logger(__name__)

_feedback_workflow = create_feedback_workflow()
_overall_feedback_workflow = create_overall_feedback_workflow()


async def run_feedback_agent(
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    session_id: str | None = None,
    callbacks: list | None = None,
) -> tuple[FeedbackOutput | None, str | None]:
    """개별 피드백 워크플로우 실행 - retrieve → generate

    Args:
        callbacks: 외부에서 주입하는 콜백 리스트 - Langfuse 부모 트레이스 묶기에 사용

    Returns:
        feedback_result, error_message 튜플
    """
    logger.info("피드백 에이전트 시작", session_id=session_id)

    try:
        initial_state: FeedbackState = {
            "position": position,
            "interview_type": interview_type,
            "question_text": question_text,
            "question_intent": question_intent,
            "related_project": related_project,
            "answer": answer,
            "session_id": session_id,
        }

        config = _build_langfuse_config(
            session_id=session_id,
            tags=["feedback", "individual", interview_type, position],
            callbacks=callbacks,
        )

        final_state = await asyncio.wait_for(
            _feedback_workflow.ainvoke(initial_state, config=config),
            timeout=settings.workflow_timeout,
        )

        if final_state.get("error_code"):
            return None, final_state.get("error_message", "피드백 생성에 실패했습니다")

        feedback_result = final_state.get("feedback_result")
        if not feedback_result:
            return None, "피드백 생성에 실패했습니다"

        logger.info("피드백 에이전트 완료", score=feedback_result.score)
        return feedback_result, None

    except asyncio.TimeoutError:
        logger.error("피드백 생성 타임아웃", timeout=settings.workflow_timeout)
        return None, f"피드백 생성 타임아웃: {settings.workflow_timeout}초 초과"

    except Exception as e:
        logger.error("피드백 에이전트 실패", error=str(e), exc_info=True)
        return None, "피드백 생성에 실패했습니다"


@traceable(run_type="chain", name="individual-feedbacks")
async def run_all_feedback_agents(tasks: list) -> list:
    """개별 피드백 태스크를 병렬 실행하고 LangSmith에서 하나의 트레이스로 묶음

    Returns:
        각 태스크 결과 리스트 (예외 포함)
    """
    return await asyncio.gather(*tasks, return_exceptions=True)


async def run_overall_feedback_agent(
    position: str,
    interview_type: str,
    qa_pairs_json: str,
    individual_feedbacks_json: str = "",
    company: str = "",
    company_talent_info: str = "",
    session_id: str | None = None,
) -> tuple[OverallFeedbackOutput | None, str | None]:
    """종합 피드백 워크플로우 실행

    Returns:
        feedback_result, error_message 튜플
    """
    logger.info("종합 피드백 에이전트 시작", session_id=session_id)

    try:
        initial_state: OverallFeedbackState = {
            "position": position,
            "interview_type": interview_type,
            "company": company,
            "company_talent_info": company_talent_info,
            "qa_pairs_json": qa_pairs_json,
            "individual_feedbacks_json": individual_feedbacks_json,
            "session_id": session_id,
        }

        config = _build_langfuse_config(
            session_id=session_id,
            tags=["feedback", "overall", interview_type, position],
        )

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
