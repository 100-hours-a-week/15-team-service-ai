from app.core.logging import get_logger
from app.domain.resume.prompts.builder import (
    build_evaluator_system_prompt,
    build_generator_system_prompt,
)
from app.domain.resume.schemas import (
    EvaluationOutput,
    ProjectInfoDict,
    ResumeData,
)
from app.domain.resume.schemas.edit import ClassifyOutput, EditPlanOutput
from app.domain.resume.schemas.plan import ProjectPlan
from app.infra.langfuse.prompt_manager import get_prompt
from app.infra.llm.base import (
    _build_langfuse_config,
    _invoke_llm,
    get_evaluator_llm,
    get_generator_llm,
)

logger = get_logger(__name__)


async def generate_resume(
    project_info: list[ProjectInfoDict],
    position: str,
    session_id: str | None = None,
    generation_plans: str = "",
    feedback: str = "",
    previous_resume_json: str = "",
) -> ResumeData:
    """Plan 기반 이력서 생성 - generation_plans 텍스트를 vLLM에 전달"""
    project_count = len(project_info)

    from app.domain.resume.prompts.generation import (
        RESUME_GENERATOR_HUMAN,
        RESUME_GENERATOR_RETRY_HUMAN,
    )

    if feedback and previous_resume_json:
        human_content = RESUME_GENERATOR_RETRY_HUMAN.format(
            previous_resume_json=previous_resume_json,
            feedback=feedback,
            project_count=str(project_count),
            generation_plans=generation_plans,
        )
        logger.debug("이력서 재생성 요청", position=position, projects=project_count)
    else:
        human_content = RESUME_GENERATOR_HUMAN.format(
            project_count=str(project_count),
            generation_plans=generation_plans,
        )
        logger.debug("이력서 생성 요청", position=position, projects=project_count)

    config = _build_langfuse_config(session_id, ["resume", "generate", position])
    system_prompt = build_generator_system_prompt(position)

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=ResumeData,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    output_count = len(result.projects) if result.projects else 0
    if output_count < project_count:
        logger.warning("프로젝트 누락", input=project_count, output=output_count)

    logger.debug("이력서 생성 완료", position=position, projects=len(result.projects))
    return result


async def evaluate_resume(
    resume_data: ResumeData,
    position: str,
    commit_messages: list[str],
    session_id: str | None = None,
) -> EvaluationOutput:
    """생성된 이력서 평가 - Gemini 사용, 커밋 근거 검증"""
    logger.debug("이력서 평가 요청", position=position)

    from app.domain.resume.prompts.evaluation import RESUME_EVALUATOR_HUMAN

    resume_json = resume_data.model_dump_json(indent=2)
    commits_text = "\n".join(commit_messages) if commit_messages else "없음"

    system_prompt = build_evaluator_system_prompt(position)
    human_content = RESUME_EVALUATOR_HUMAN.format(
        position=position,
        resume_json=resume_json,
        commit_messages=commits_text,
    )

    config = _build_langfuse_config(session_id, ["resume", "evaluate", position])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=EvaluationOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug(
        "이력서 평가 완료",
        position=position,
        result=result.result,
        violated_rule=result.violated_rule,
    )
    return result


async def classify_edit(
    resume_json: str,
    message: str,
    session_id: str | None = None,
) -> ClassifyOutput:
    """이력서 수정 요청 분류 - Gemini 사용"""
    logger.debug("이력서 수정 요청 분류 시작")

    system_prompt = get_prompt("resume-edit-classify-system")
    human_content = get_prompt(
        "resume-edit-classify-human",
        resume_json=resume_json,
        message=message,
    )
    config = _build_langfuse_config(session_id, ["resume", "edit-classify"])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=ClassifyOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug(
        "수정 요청 분류 완료",
        category=result.intent_category,
        confidence=result.confidence,
    )
    return result


async def plan_edit(
    resume_json: str,
    message: str,
    session_id: str | None = None,
) -> EditPlanOutput:
    """이력서 수정 계획 생성 - Gemini 사용

    사용자 요청을 분석하여 vLLM에게 전달할 구체적인 수정 지시를 생성한다.
    """
    logger.debug("이력서 수정 계획 요청")

    system_prompt = get_prompt("resume-edit-plan-system")
    human_content = get_prompt(
        "resume-edit-plan-human",
        resume_json=resume_json,
        message=message,
    )
    config = _build_langfuse_config(session_id, ["resume", "edit-plan"])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=EditPlanOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug(
        "수정 계획 생성 완료",
        edit_type=result.edit_type,
        target=result.target_summary,
    )
    return result


async def plan_resume(
    project_info: dict,
    position: str,
    repo_context: dict | None = None,
    session_id: str | None = None,
) -> ProjectPlan:
    """Gemini로 프로젝트 1개의 이력서 생성 계획 수행"""
    logger.debug("이력서 Plan 요청", project=project_info.get("repo_name"), position=position)

    from app.domain.resume.prompts.plan import RESUME_PLAN_HUMAN, RESUME_PLAN_SYSTEM
    from app.domain.resume.prompts.positions import get_position_rules

    position_rules = get_position_rules(position)

    system_prompt = RESUME_PLAN_SYSTEM.format(
        position=position,
        position_rules=position_rules,
    )

    messages_text = "\n".join(project_info.get("messages", []))
    dependencies_text = ", ".join(project_info.get("dependencies", []))

    languages = ""
    description = ""
    readme_summary = ""
    if repo_context:
        languages = str(repo_context.get("languages", ""))
        description = repo_context.get("description", "") or ""
        readme_summary = repo_context.get("readme_summary", "") or ""

    human_content = RESUME_PLAN_HUMAN.format(
        position=position,
        project_name=project_info.get("repo_name", ""),
        repo_url=project_info.get("repo_url", ""),
        messages=messages_text,
        dependencies=dependencies_text,
        languages=languages,
        description=description,
        readme_summary=readme_summary,
    )

    config = _build_langfuse_config(session_id, ["resume", "plan", position])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=ProjectPlan,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug(
        "이력서 Plan 완료",
        project=result.project_name,
        bullets=len(result.bullet_plans),
        tech_stack=len(result.recommended_tech_stack),
    )
    return result


async def edit_resume[T](
    resume_json: str,
    message: str,
    output_type: type[T],
    feedback: str | None = None,
    session_id: str | None = None,
) -> T:
    """이력서 수정 - vLLM 사용"""
    logger.debug("이력서 수정 요청")

    if feedback:
        human_content = get_prompt(
            "resume-edit-retry-human",
            resume_json=resume_json,
            message=message,
            feedback=feedback,
        )
    else:
        human_content = get_prompt(
            "resume-edit-human",
            resume_json=resume_json,
            message=message,
        )

    system_prompt = get_prompt("resume-edit-system")
    config = _build_langfuse_config(session_id, ["resume", "edit"])

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=output_type,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug("이력서 수정 완료")
    return result


async def evaluate_edited_resume(
    resume_json: str,
    session_id: str | None = None,
    user_message: str = "",
) -> EvaluationOutput:
    """수정된 이력서 평가 - Gemini 사용, 포지션 체크 없음"""
    logger.debug("수정 이력서 평가 요청")

    human_content = get_prompt(
        "resume-edit-evaluator-human",
        resume_json=resume_json,
        user_message=user_message,
    )

    system_prompt = get_prompt("resume-edit-evaluator-system")
    config = _build_langfuse_config(session_id, ["resume", "edit-evaluate"])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=EvaluationOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
        structured_output_method="json_mode",
    )

    logger.debug(
        "수정 이력서 평가 완료",
        result=result.result,
        rule=result.violated_rule,
        item=result.violated_item,
        feedback=result.feedback,
    )
    return result
