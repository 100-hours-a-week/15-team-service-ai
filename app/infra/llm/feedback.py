from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interview.feedback_schemas import (
    FeedbackOutput,
    OverallFeedbackOutput,
    RetrievalEvalOutput,
)
from app.domain.interview.prompts.feedback_templates import (
    LOCAL_FEEDBACK_RETRIEVAL_EVALUATOR_HUMAN,
    LOCAL_FEEDBACK_RETRIEVAL_EVALUATOR_SYSTEM,
)
from app.infra.langfuse.prompt_manager import get_prompt
from app.infra.llm.base import (
    _VALID_INTERVIEW_TYPES,
    _build_langfuse_config,
    _invoke_llm,
    get_evaluator_llm,
    get_generator_llm,
)

logger = get_logger(__name__)


async def generate_feedback(
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    retrieved_context: str = "",
    feedback: str | None = None,
    session_id: str | None = None,
    callbacks: list | None = None,
) -> FeedbackOutput:
    """면접 피드백 생성 - vLLM 사용"""
    if interview_type not in _VALID_INTERVIEW_TYPES:
        raise ValueError(f"지원하지 않는 면접 유형: {interview_type}")
    logger.debug("피드백 생성 요청", interview_type=interview_type, position=position)

    related_project_text = related_project or "없음"

    common_vars = {
        "position": position,
        "question_text": question_text,
        "question_intent": question_intent,
        "related_project": related_project_text,
        "answer": answer,
    }
    if interview_type == "technical":
        common_vars["retrieved_context"] = retrieved_context

    if feedback:
        human_content = get_prompt(
            f"feedback-{interview_type}-retry-human",
            feedback=feedback,
            **common_vars,
        )
    else:
        human_content = get_prompt(
            f"feedback-{interview_type}-human",
            **common_vars,
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
    individual_feedbacks_json: str = "",
    company: str = "",
    company_talent_info: str = "",
    session_id: str | None = None,
    callbacks: list | None = None,
) -> OverallFeedbackOutput:
    """종합 면접 피드백 생성 - vLLM 사용"""
    if interview_type not in _VALID_INTERVIEW_TYPES:
        raise ValueError(f"지원하지 않는 면접 유형: {interview_type}")
    logger.debug(
        "종합 피드백 생성 요청",
        interview_type=interview_type,
        position=position,
        company=company,
        has_talent_info=bool(company_talent_info),
    )

    human_content = get_prompt(
        f"feedback-overall-{interview_type}-human",
        position=position,
        qa_pairs_json=qa_pairs_json,
        individual_feedbacks_json=individual_feedbacks_json,
        company=company or "미지정",
        company_talent_info=company_talent_info or "없음",
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


async def evaluate_retrieval_quality(
    question_text: str,
    question_intent: str,
    retrieved_context: str,
    session_id: str | None = None,
    callbacks: list | None = None,
) -> RetrievalEvalOutput:
    """Retrieval 품질 평가 - Gemini 사용

    Returns:
        RetrievalEvalOutput with result ("pass"/"fail") and reason
    """
    if not settings.gemini_api_key or not settings.gemini_evaluator_model:
        raise ValueError("Gemini 설정 누락 - retrieval 평가 스킵")

    human_content = LOCAL_FEEDBACK_RETRIEVAL_EVALUATOR_HUMAN.format(
        question_text=question_text,
        question_intent=question_intent,
        retrieved_context=retrieved_context or "없음",
    )
    config = _build_langfuse_config(
        session_id,
        ["retrieval-eval"],
        callbacks=callbacks,
    )

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=RetrievalEvalOutput,
        system_prompt=LOCAL_FEEDBACK_RETRIEVAL_EVALUATOR_SYSTEM,
        human_content=human_content,
        config=config,
    )

    logger.debug("retrieval 품질 평가 완료", result=result.result, reason=result.reason)
    return result
