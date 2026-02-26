from app.core.logging import get_logger
from app.domain.interview.schemas import InterviewEvaluationOutput, InterviewQuestionsOutput
from app.domain.resume.prompts.positions import get_interview_position_focus
from app.infra.langfuse.prompt_manager import get_prompt
from app.infra.llm.base import (
    _build_langfuse_config,
    _invoke_llm,
    get_evaluator_llm,
    get_generator_llm,
)

logger = get_logger(__name__)

_VALID_INTERVIEW_TYPES = frozenset({"technical", "behavioral"})


async def generate_interview(
    resume_json: str,
    interview_type: str,
    position: str,
    question_count: int,
    feedback: str | None = None,
    session_id: str | None = None,
) -> InterviewQuestionsOutput:
    """면접 질문 생성 - vLLM 사용"""
    if interview_type not in _VALID_INTERVIEW_TYPES:
        raise ValueError(f"지원하지 않는 면접 유형: {interview_type}")
    logger.debug("면접 질문 생성 요청", interview_type=interview_type, position=position)

    if feedback:
        human_content = get_prompt(
            f"interview-{interview_type}-retry-human",
            position=position,
            resume_json=resume_json,
            feedback=feedback,
            question_count=str(question_count),
        )
    else:
        human_content = get_prompt(
            f"interview-{interview_type}-human",
            position=position,
            resume_json=resume_json,
            question_count=str(question_count),
        )

    position_focus = get_interview_position_focus(position)
    system_prompt = get_prompt(
        f"interview-{interview_type}-system",
        position_focus=position_focus,
        question_count=str(question_count),
    )
    config = _build_langfuse_config(session_id, ["interview", interview_type, position])

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=InterviewQuestionsOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug("면접 질문 생성 완료", questions=len(result.questions))
    return result


async def evaluate_interview(
    questions_json: str,
    resume_json: str,
    interview_type: str,
    question_count: int,
    session_id: str | None = None,
) -> InterviewEvaluationOutput:
    """면접 질문 평가 - Gemini 사용"""
    logger.debug("면접 질문 평가 요청", interview_type=interview_type)

    human_content = get_prompt(
        "interview-evaluator-human",
        interview_type=interview_type,
        resume_json=resume_json,
        questions_json=questions_json,
    )

    system_prompt = get_prompt(
        "interview-evaluator-system",
        question_count=str(question_count),
    )
    config = _build_langfuse_config(session_id, ["interview", "evaluate", interview_type])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=InterviewEvaluationOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug(
        "면접 질문 평가 완료",
        result=result.result,
        rule=result.violated_rule,
        item=result.violated_item,
        feedback=result.feedback,
    )
    return result
