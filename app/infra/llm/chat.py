from app.core.logging import get_logger
from app.domain.interview.chat_schemas import ChatOutput
from app.infra.langfuse.prompt_manager import get_prompt
from app.infra.llm.base import _build_langfuse_config, _invoke_llm, get_generator_llm

logger = get_logger(__name__)


async def generate_chat_response(
    resume_json: str,
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    session_id: str | None = None,
) -> ChatOutput:
    """면접 채팅 응답 생성 - vLLM 사용"""
    logger.debug(
        "채팅 응답 생성 요청",
        interview_type=interview_type,
        position=position,
    )

    related_project_text = related_project or "없음"

    human_content = get_prompt(
        f"chat-{interview_type}-human",
        question_text=question_text,
        question_intent=question_intent,
        related_project=related_project_text,
        answer=answer,
    )

    system_prompt = get_prompt(
        f"chat-{interview_type}-system",
        position=position,
        resume_json=resume_json,
    )
    config = _build_langfuse_config(session_id, ["chat", interview_type, position])

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=ChatOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug("채팅 응답 생성 완료")
    return result


async def generate_chat_response_with_history(
    resume_json: str,
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    conversation_history: str,
    session_id: str | None = None,
) -> ChatOutput:
    """멀티턴 면접 채팅 응답 생성 - 대화 이력 포함, vLLM 사용"""
    logger.debug(
        "멀티턴 채팅 응답 생성 요청",
        interview_type=interview_type,
        position=position,
    )

    related_project_text = related_project or "없음"

    human_content = get_prompt(
        f"chat-{interview_type}-human-multiturn",
        question_text=question_text,
        question_intent=question_intent,
        related_project=related_project_text,
        answer=answer,
        conversation_history=conversation_history,
    )

    system_prompt = get_prompt(
        f"chat-{interview_type}-system",
        position=position,
        resume_json=resume_json,
    )
    config = _build_langfuse_config(session_id, ["chat", "multiturn", interview_type, position])

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=ChatOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug("멀티턴 채팅 응답 생성 완료")
    return result
