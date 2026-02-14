import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interview.schemas import InterviewQuestionsOutput, InterviewState
from app.domain.interview.workflow import create_interview_workflow
from app.infra.llm.client import get_langfuse_handler

logger = get_logger(__name__)

_interview_workflow = create_interview_workflow()


async def run_interview_agent(
    resume_json: str,
    interview_type: str,
    position: str,
    session_id: str | None = None,
) -> tuple[InterviewQuestionsOutput | None, str | None]:
    """면접 질문 생성 워크플로우 실행

    Returns:
        questions, error_message 튜플
    """
    logger.info("면접 에이전트 시작", session_id=session_id)

    try:
        initial_state: InterviewState = {
            "resume_json": resume_json,
            "interview_type": interview_type,
            "position": position,
            "session_id": session_id,
            "retry_count": 0,
        }

        langfuse_handler = get_langfuse_handler()
        config = {"callbacks": [langfuse_handler]} if langfuse_handler else {}

        final_state = await asyncio.wait_for(
            _interview_workflow.ainvoke(initial_state, config=config),
            timeout=settings.workflow_timeout,
        )

        if final_state.get("error_code"):
            error_msg = final_state.get("error_message", "알 수 없는 오류")
            logger.error("면접 워크플로우 실패", error_code=final_state.get("error_code"))
            return None, error_msg

        questions = final_state.get("questions")
        if not questions:
            return None, "면접 질문 생성 실패"

        logger.info("면접 에이전트 완료", questions=len(questions.questions))
        return questions, None

    except asyncio.TimeoutError:
        logger.error("면접 워크플로우 타임아웃", timeout=settings.workflow_timeout)
        return None, f"워크플로우 타임아웃: {settings.workflow_timeout}초 초과"

    except Exception as e:
        logger.error("면접 에이전트 실패", error=str(e), exc_info=True)
        return None, "알 수 없는 오류가 발생했습니다"
