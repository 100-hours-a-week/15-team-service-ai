import re

from app.core.exceptions import LLMError
from app.core.logging import get_logger
from langfuse import Langfuse

logger = get_logger(__name__)

_langfuse_client: Langfuse | None = None


def _get_client() -> Langfuse:
    """Langfuse 클라이언트 싱글턴 반환"""
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    _langfuse_client = Langfuse()
    return _langfuse_client


def _render(template: str, **variables: str) -> str:
    """템플릿 포맷 자동 감지 후 변수 치환

    - {{variable}} 포맷(Langfuse): regex 치환 - JSON 예시의 { } 충돌 없음
    - {variable} 포맷(Python): str.format() - resume 프롬프트용
    """
    if "{{" in template:

        def _replace(m: re.Match) -> str:
            var_name = m.group(1)
            if var_name not in variables:
                logger.warning("프롬프트 변수 누락", variable=var_name)
            return variables.get(var_name, "")

        return re.sub(r"\{\{(\w+)\}\}", _replace, template)
    return template.format(**variables) if variables else template


def _get_local_fallback(name: str, **variables: str) -> str:
    """Langfuse 조회 실패 시 로컬 상수로 fallback"""
    from app.domain.interview.prompts.chat_templates import (
        CHAT_BEHAVIORAL_HUMAN,
        CHAT_BEHAVIORAL_HUMAN_MULTITURN,
        CHAT_BEHAVIORAL_SYSTEM,
        CHAT_TECHNICAL_HUMAN,
        CHAT_TECHNICAL_HUMAN_MULTITURN,
        CHAT_TECHNICAL_SYSTEM,
    )
    from app.domain.interview.prompts.feedback_templates import (
        FEEDBACK_BEHAVIORAL_HUMAN,
        FEEDBACK_BEHAVIORAL_RETRY_HUMAN,
        FEEDBACK_BEHAVIORAL_SYSTEM,
        FEEDBACK_EVALUATOR_HUMAN,
        FEEDBACK_EVALUATOR_SYSTEM,
        FEEDBACK_OVERALL_BEHAVIORAL_HUMAN,
        FEEDBACK_OVERALL_BEHAVIORAL_SYSTEM,
        FEEDBACK_OVERALL_TECHNICAL_HUMAN,
        FEEDBACK_OVERALL_TECHNICAL_SYSTEM,
        FEEDBACK_TECHNICAL_HUMAN,
        FEEDBACK_TECHNICAL_RETRY_HUMAN,
        FEEDBACK_TECHNICAL_SYSTEM,
    )
    from app.domain.interview.prompts.templates import (
        INTERVIEW_BEHAVIORAL_HUMAN,
        INTERVIEW_BEHAVIORAL_RETRY_HUMAN,
        INTERVIEW_BEHAVIORAL_SYSTEM,
        INTERVIEW_EVALUATOR_HUMAN,
        INTERVIEW_EVALUATOR_SYSTEM,
        INTERVIEW_TECHNICAL_HUMAN,
        INTERVIEW_TECHNICAL_RETRY_HUMAN,
        INTERVIEW_TECHNICAL_SYSTEM,
    )
    from app.domain.resume.prompts.edit import (
        RESUME_EDIT_CLASSIFY_HUMAN,
        RESUME_EDIT_CLASSIFY_SYSTEM,
        RESUME_EDIT_EVALUATOR_HUMAN,
        RESUME_EDIT_EVALUATOR_SYSTEM,
        RESUME_EDIT_HUMAN,
        RESUME_EDIT_PLAN_HUMAN,
        RESUME_EDIT_PLAN_SYSTEM,
        RESUME_EDIT_RETRY_HUMAN,
        RESUME_EDIT_SYSTEM,
    )
    from app.domain.resume.prompts.evaluation import RESUME_EVALUATOR_HUMAN, RESUME_EVALUATOR_SYSTEM
    from app.domain.resume.prompts.generation import (
        RESUME_GENERATOR_HUMAN,
        RESUME_GENERATOR_RETRY_HUMAN,
        RESUME_GENERATOR_SYSTEM,
    )
    from app.domain.resume.prompts.plan import RESUME_PLAN_HUMAN, RESUME_PLAN_SYSTEM

    registry: dict[str, str] = {
        "resume-evaluator-system": RESUME_EVALUATOR_SYSTEM,
        "resume-evaluator-human": RESUME_EVALUATOR_HUMAN,
        "resume-plan-system": RESUME_PLAN_SYSTEM,
        "resume-plan-human": RESUME_PLAN_HUMAN,
        "resume-generator-system": RESUME_GENERATOR_SYSTEM,
        "resume-generator-human": RESUME_GENERATOR_HUMAN,
        "resume-generator-retry-human": RESUME_GENERATOR_RETRY_HUMAN,
        "resume-edit-classify-system": RESUME_EDIT_CLASSIFY_SYSTEM,
        "resume-edit-classify-human": RESUME_EDIT_CLASSIFY_HUMAN,
        "resume-edit-plan-system": RESUME_EDIT_PLAN_SYSTEM,
        "resume-edit-plan-human": RESUME_EDIT_PLAN_HUMAN,
        "resume-edit-system": RESUME_EDIT_SYSTEM,
        "resume-edit-human": RESUME_EDIT_HUMAN,
        "resume-edit-retry-human": RESUME_EDIT_RETRY_HUMAN,
        "resume-edit-evaluator-system": RESUME_EDIT_EVALUATOR_SYSTEM,
        "resume-edit-evaluator-human": RESUME_EDIT_EVALUATOR_HUMAN,
        "interview-technical-system": INTERVIEW_TECHNICAL_SYSTEM,
        "interview-technical-human": INTERVIEW_TECHNICAL_HUMAN,
        "interview-technical-retry-human": INTERVIEW_TECHNICAL_RETRY_HUMAN,
        "interview-behavioral-system": INTERVIEW_BEHAVIORAL_SYSTEM,
        "interview-behavioral-human": INTERVIEW_BEHAVIORAL_HUMAN,
        "interview-behavioral-retry-human": INTERVIEW_BEHAVIORAL_RETRY_HUMAN,
        "interview-evaluator-system": INTERVIEW_EVALUATOR_SYSTEM,
        "interview-evaluator-human": INTERVIEW_EVALUATOR_HUMAN,
        "chat-technical-system": CHAT_TECHNICAL_SYSTEM,
        "chat-technical-human": CHAT_TECHNICAL_HUMAN,
        "chat-technical-human-multiturn": CHAT_TECHNICAL_HUMAN_MULTITURN,
        "chat-behavioral-system": CHAT_BEHAVIORAL_SYSTEM,
        "chat-behavioral-human": CHAT_BEHAVIORAL_HUMAN,
        "chat-behavioral-human-multiturn": CHAT_BEHAVIORAL_HUMAN_MULTITURN,
        "feedback-technical-system": FEEDBACK_TECHNICAL_SYSTEM,
        "feedback-technical-human": FEEDBACK_TECHNICAL_HUMAN,
        "feedback-technical-retry-human": FEEDBACK_TECHNICAL_RETRY_HUMAN,
        "feedback-behavioral-system": FEEDBACK_BEHAVIORAL_SYSTEM,
        "feedback-behavioral-human": FEEDBACK_BEHAVIORAL_HUMAN,
        "feedback-behavioral-retry-human": FEEDBACK_BEHAVIORAL_RETRY_HUMAN,
        "feedback-overall-technical-system": FEEDBACK_OVERALL_TECHNICAL_SYSTEM,
        "feedback-overall-technical-human": FEEDBACK_OVERALL_TECHNICAL_HUMAN,
        "feedback-overall-behavioral-system": FEEDBACK_OVERALL_BEHAVIORAL_SYSTEM,
        "feedback-overall-behavioral-human": FEEDBACK_OVERALL_BEHAVIORAL_HUMAN,
        "feedback-evaluator-system": FEEDBACK_EVALUATOR_SYSTEM,
        "feedback-evaluator-human": FEEDBACK_EVALUATOR_HUMAN,
    }

    if name not in registry:
        raise LLMError(detail=f"프롬프트 조회 실패 및 fallback 없음: {name}")

    logger.warning("로컬 fallback 프롬프트 사용", prompt_name=name)
    return _render(registry[name], **variables)


def get_prompt(name: str, **variables: str) -> str:
    """Langfuse에서 프롬프트 조회 후 변수 치환, 실패 시 로컬 fallback

    name: Langfuse에 등록된 프롬프트 이름
    variables: 프롬프트에 주입할 변수들
    """
    client = _get_client()

    try:
        prompt = client.get_prompt(name)
    except Exception as e:
        logger.warning("Langfuse 프롬프트 조회 실패, fallback 시도", prompt_name=name, error=str(e))
        return _get_local_fallback(name, **variables)

    try:
        compiled = prompt.compile(**variables)
    except KeyError as e:
        logger.error("프롬프트 변수 누락", prompt_name=name, variable=str(e), exc_info=True)
        raise LLMError(detail=f"프롬프트 '{name}'에 필요한 변수 누락: {e}") from e

    logger.debug("Langfuse 프롬프트 사용", prompt_name=name)
    return compiled
