import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.resume.edit_workflow import create_edit_workflow
from app.domain.resume.schemas.edit import EditResumeOutput, EditState
from app.infra.llm.client import get_langfuse_handler

logger = get_logger(__name__)

_edit_workflow = create_edit_workflow()


async def run_edit_agent(
    resume_json: str,
    message: str,
    session_id: str | None = None,
) -> tuple[EditResumeOutput | None, str | None]:
    """이력서 수정 워크플로우 실행

    Returns:
        edited_resume, error_message 튜플
    """
    logger.info("수정 에이전트 시작", session_id=session_id)

    try:
        initial_state: EditState = {
            "resume_json": resume_json,
            "message": message,
            "session_id": session_id,
            "retry_count": 0,
        }

        langfuse_handler = get_langfuse_handler()
        config = {"callbacks": [langfuse_handler]} if langfuse_handler else {}

        final_state = await asyncio.wait_for(
            _edit_workflow.ainvoke(initial_state, config=config),
            timeout=settings.workflow_timeout,
        )

        if final_state.get("error_code"):
            error_msg = final_state.get("error_message", "알 수 없는 오류")
            logger.error("수정 워크플로우 실패", error_code=final_state.get("error_code"))
            return None, error_msg

        edited_resume = final_state.get("edited_resume")
        if not edited_resume:
            return None, "이력서 수정 실패"

        logger.info("수정 에이전트 완료", projects=len(edited_resume.projects))
        return edited_resume, None

    except asyncio.TimeoutError:
        logger.error("수정 워크플로우 타임아웃", timeout=settings.workflow_timeout)
        return None, f"워크플로우 타임아웃: {settings.workflow_timeout}초 초과"

    except Exception as e:
        logger.error("수정 에이전트 실패", error=str(e), exc_info=True)
        return None, "알 수 없는 오류가 발생했습니다"
