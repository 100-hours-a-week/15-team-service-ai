import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.resume.schemas import ResumeData, ResumeRequest, ResumeState
from app.domain.resume.workflow import create_resume_workflow
from app.infra.llm.client import get_langfuse_handler

logger = get_logger(__name__)


async def run_resume_agent(
    request: ResumeRequest,
    session_id: str | None = None,
) -> tuple[ResumeData | None, str | None]:
    """에이전트 기반 이력서 생성 워크플로우

    Args:
        request: 이력서 생성 요청
        session_id: Langfuse 세션 ID

    Returns:
        resume_data, error_message 튜플
    """
    logger.info(
        "에이전트 시작 repos=%d position=%s session_id=%s",
        len(request.repo_urls),
        request.position,
        session_id,
    )

    try:
        workflow = create_resume_workflow()

        initial_state: ResumeState = {
            "request": request,
            "session_id": session_id,
        }

        langfuse_handler = get_langfuse_handler()
        config = {"callbacks": [langfuse_handler]} if langfuse_handler else {}

        final_state = await asyncio.wait_for(
            workflow.ainvoke(initial_state, config=config),
            timeout=settings.workflow_timeout,
        )

        if final_state.get("error_code"):
            error_msg = final_state.get("error_message", "알 수 없는 오류")
            logger.error("워크플로우 실패 error_code=%s", final_state.get("error_code"))
            return None, error_msg

        resume_data = final_state.get("resume_data")
        if not resume_data:
            return None, "이력서 생성 실패"

        logger.info("에이전트 완료 projects=%d", len(resume_data.projects))
        return resume_data, None

    except asyncio.TimeoutError:
        logger.error("워크플로우 타임아웃 timeout=%ds", settings.workflow_timeout)
        return None, f"워크플로우 타임아웃: {settings.workflow_timeout}초 초과"

    except Exception as e:
        logger.error("에이전트 실패 error=%s", e, exc_info=True)
        return None, str(e)
