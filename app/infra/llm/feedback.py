from app.core.logging import get_logger
from app.domain.interview.feedback_schemas import (
    FeedbackOutput,
    OverallFeedbackOutput,
)
from app.infra.langfuse.prompt_manager import get_prompt
from app.infra.llm.base import (
    _build_langfuse_config,
    _invoke_llm,
    get_generator_llm,
)

logger = get_logger(__name__)

_VALID_INTERVIEW_TYPES = frozenset({"technical", "behavioral"})


async def generate_feedback(
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    feedback: str | None = None,
    session_id: str | None = None,
    callbacks: list | None = None,
) -> FeedbackOutput:
    """면접 피드백 생성 - vLLM 사용"""
    if interview_type not in _VALID_INTERVIEW_TYPES:
        raise ValueError(f"지원하지 않는 면접 유형: {interview_type}")
    logger.debug("피드백 생성 요청", interview_type=interview_type, position=position)

    related_project_text = related_project or "없음"

    if feedback:
        human_content = get_prompt(
            f"feedback-{interview_type}-retry-human",
            position=position,
            question_text=question_text,
            question_intent=question_intent,
            related_project=related_project_text,
            answer=answer,
            feedback=feedback,
        )
    else:
        human_content = get_prompt(
            f"feedback-{interview_type}-human",
            position=position,
            question_text=question_text,
            question_intent=question_intent,
            related_project=related_project_text,
            answer=answer,
        )

    system_prompt = get_prompt(f"feedback-{interview_type}-system")
    config = _build_langfuse_config(
        session_id,
        ["feedback", interview_type, position],
        callbacks=callbacks,
    )

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=FeedbackOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug("피드백 생성 완료", score=result.score)
    return result


async def generate_overall_feedback(
    position: str,
    interview_type: str,
    qa_pairs_json: str,
    session_id: str | None = None,
    callbacks: list | None = None,
) -> OverallFeedbackOutput:
    """종합 면접 피드백 생성 - vLLM 사용"""
    if interview_type not in _VALID_INTERVIEW_TYPES:
        raise ValueError(f"지원하지 않는 면접 유형: {interview_type}")
    logger.debug("종합 피드백 생성 요청", interview_type=interview_type, position=position)

    human_content = get_prompt(
        f"feedback-overall-{interview_type}-human",
        position=position,
        qa_pairs_json=qa_pairs_json,
    )

    system_prompt = get_prompt(f"feedback-overall-{interview_type}-system")
    config = _build_langfuse_config(
        session_id,
        ["feedback", "overall", interview_type, position],
        callbacks=callbacks,
    )

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=OverallFeedbackOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug("종합 피드백 생성 완료", overall_score=result.overall_score)
    return result
