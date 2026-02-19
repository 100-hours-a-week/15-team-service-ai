import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interview.chat_schemas import ChatOutput
from app.infra.llm.client import generate_chat_response

logger = get_logger(__name__)


async def run_chat_agent(
    resume_json: str,
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    session_id: str | None = None,
) -> tuple[ChatOutput | None, str | None]:
    """면접 채팅 에이전트 실행 - 워크플로우 없이 단일 LLM 호출

    Returns:
        chat_result, error_message 튜플
    """
    logger.info("채팅 에이전트 시작", session_id=session_id)

    try:
        result = await asyncio.wait_for(
            generate_chat_response(
                resume_json=resume_json,
                position=position,
                interview_type=interview_type,
                question_text=question_text,
                question_intent=question_intent,
                related_project=related_project,
                answer=answer,
                session_id=session_id,
            ),
            timeout=settings.workflow_timeout,
        )

        logger.info("채팅 에이전트 완료")
        return result, None

    except asyncio.TimeoutError:
        logger.error(
            "채팅 응답 타임아웃",
            timeout=settings.workflow_timeout,
        )
        return None, f"채팅 응답 타임아웃: {settings.workflow_timeout}초 초과"

    except Exception as e:
        logger.error("채팅 에이전트 실패", error=str(e), exc_info=True)
        return None, "채팅 응답 생성에 실패했습니다"
