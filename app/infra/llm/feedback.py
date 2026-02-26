from app.core.logging import get_logger
from app.domain.interview.feedback_schemas import (
    FeedbackEvaluationOutput,
    FeedbackOutput,
    OverallFeedbackEvaluationOutput,
    OverallFeedbackOutput,
)
from app.infra.langfuse.prompt_manager import get_prompt
from app.infra.llm.base import (
    _build_langfuse_config,
    _invoke_llm,
    get_evaluator_llm,
    get_generator_llm,
)

logger = get_logger(__name__)

_VALID_INTERVIEW_TYPES = frozenset({"technical", "behavioral"})


async def generate_feedback(
    resume_json: str,
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    feedback: str | None = None,
    session_id: str | None = None,
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
            resume_json=resume_json,
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
            resume_json=resume_json,
            question_text=question_text,
            question_intent=question_intent,
            related_project=related_project_text,
            answer=answer,
        )

    system_prompt = get_prompt(f"feedback-{interview_type}-system")
    config = _build_langfuse_config(session_id, ["feedback", interview_type, position])

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


async def evaluate_feedback(
    feedback_json: str,
    question_text: str,
    answer: str,
    interview_type: str,
    session_id: str | None = None,
) -> FeedbackEvaluationOutput:
    """면접 피드백 평가 - Gemini 사용"""
    logger.debug("피드백 평가 요청", interview_type=interview_type)

    human_content = get_prompt(
        "feedback-evaluator-human",
        interview_type=interview_type,
        question_text=question_text,
        answer=answer,
        feedback_json=feedback_json,
    )

    system_prompt = get_prompt("feedback-evaluator-system")
    config = _build_langfuse_config(session_id, ["feedback", "evaluate", interview_type])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=FeedbackEvaluationOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug("피드백 평가 완료", result=result.result)
    return result


async def generate_overall_feedback(
    resume_json: str,
    position: str,
    interview_type: str,
    qa_pairs_json: str,
    feedback: str | None = None,
    session_id: str | None = None,
) -> OverallFeedbackOutput:
    """종합 면접 피드백 생성 - vLLM 사용"""
    if interview_type not in _VALID_INTERVIEW_TYPES:
        raise ValueError(f"지원하지 않는 면접 유형: {interview_type}")
    logger.debug("종합 피드백 생성 요청", interview_type=interview_type, position=position)

    if feedback:
        human_content = get_prompt(
            f"feedback-overall-{interview_type}-retry-human",
            position=position,
            resume_json=resume_json,
            qa_pairs_json=qa_pairs_json,
            feedback=feedback,
        )
    else:
        human_content = get_prompt(
            f"feedback-overall-{interview_type}-human",
            position=position,
            resume_json=resume_json,
            qa_pairs_json=qa_pairs_json,
        )

    system_prompt = get_prompt(f"feedback-overall-{interview_type}-system")
    config = _build_langfuse_config(session_id, ["feedback", "overall", interview_type, position])

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


async def evaluate_overall_feedback(
    overall_feedback_json: str,
    qa_pairs_json: str,
    interview_type: str,
    session_id: str | None = None,
) -> OverallFeedbackEvaluationOutput:
    """종합 면접 피드백 평가 - Gemini 사용"""
    logger.debug("종합 피드백 평가 요청", interview_type=interview_type)

    human_content = get_prompt(
        "feedback-overall-evaluator-human",
        interview_type=interview_type,
        qa_pairs_json=qa_pairs_json,
        overall_feedback_json=overall_feedback_json,
    )

    system_prompt = get_prompt("feedback-overall-evaluator-system")
    config = _build_langfuse_config(session_id, ["feedback", "overall", "evaluate", interview_type])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=OverallFeedbackEvaluationOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug("종합 피드백 평가 완료", result=result.result)
    return result
