from app.core.logging import get_logger
from app.domain.resume.prompts.builder import (
    build_evaluator_system_prompt,
    build_generator_system_prompt,
    format_project_info,
    format_repo_contexts,
)
from app.domain.resume.schemas import (
    EvaluationOutput,
    ProjectInfoDict,
    RepoContext,
    ResumeData,
    UserStats,
)
from app.domain.resume.schemas.edit import ClassifyOutput, EditPlanOutput
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
    repo_urls: list[str],
    feedback: str | None = None,
    repo_contexts: dict[str, RepoContext] | None = None,
    user_stats: UserStats | None = None,
    session_id: str | None = None,
    previous_resume: ResumeData | None = None,
) -> ResumeData:
    """프로젝트 정보 기반 이력서 생성"""
    logger.debug("이력서 생성 요청", position=position, projects=len(project_info))

    project_info_text = format_project_info(project_info)
    repo_urls_text = "\n".join(repo_urls)

    contexts_text = format_repo_contexts(repo_contexts)

    if user_stats:
        user_stats_text = (
            f"총 커밋: {user_stats.total_commits}개, "
            f"총 PR: {user_stats.total_prs}개, "
            f"총 이슈: {user_stats.total_issues}개"
        )
    else:
        user_stats_text = "없음"

    project_count = len(project_info)

    if feedback:
        previous_resume_json = (
            previous_resume.model_dump_json(indent=2) if previous_resume else "{}"
        )
        human_content = get_prompt(
            "resume-generator-retry-human",
            position=position,
            project_info=project_info_text,
            repo_urls=repo_urls_text,
            feedback=feedback,
            repo_contexts=contexts_text,
            user_stats=user_stats_text,
            project_count=str(project_count),
            previous_resume_json=previous_resume_json,
        )
    else:
        human_content = get_prompt(
            "resume-generator-human",
            position=position,
            project_info=project_info_text,
            repo_urls=repo_urls_text,
            repo_contexts=contexts_text,
            user_stats=user_stats_text,
            project_count=str(project_count),
        )

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
    commit_messages: list[str] | None = None,
    session_id: str | None = None,
) -> EvaluationOutput:
    """이력서 품질 평가"""
    logger.debug("이력서 평가 요청", position=position)

    resume_json = resume_data.model_dump_json(indent=2)
    commits_text = "\n".join(commit_messages) if commit_messages else "없음"

    human_content = get_prompt(
        "resume-evaluator-human",
        position=position,
        resume_json=resume_json,
        commit_messages=commits_text,
    )

    config = _build_langfuse_config(session_id, ["resume", "evaluate", position])
    system_prompt = build_evaluator_system_prompt(position)

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
        result=result.result,
        rule=result.violated_rule,
        item=result.violated_item,
        feedback=result.feedback,
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
