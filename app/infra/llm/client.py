import json
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.resume.prompts import (
    RESUME_EVALUATOR_HUMAN,
    RESUME_EVALUATOR_SYSTEM,
    RESUME_GENERATOR_HUMAN,
    RESUME_GENERATOR_RETRY_HUMAN,
    RESUME_GENERATOR_SYSTEM,
)
from app.domain.resume.schemas import (
    EvaluationOutput,
    RepoContext,
    ResumeData,
    UserStats,
)

logger = get_logger(__name__)

if settings.langfuse_public_key:
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
if settings.langfuse_secret_key:
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
if settings.langfuse_base_url:
    os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url


def get_langfuse_handler(
    session_id: str | None = None,
    trace_name: str | None = None,
    tags: list[str] | None = None,
) -> CallbackHandler | None:
    """Langfuse 콜백 핸들러 반환"""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    return CallbackHandler(
        session_id=session_id,
        trace_name=trace_name,
        tags=tags or [],
    )


def get_llm(model: str, callbacks: list | None = None) -> ChatOpenAI:
    """OpenAI LLM 클라이언트 반환"""
    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout,
        temperature=0,
        callbacks=callbacks,
    )


def format_project_info(project_info: list[dict]) -> str:
    """프로젝트 정보를 프롬프트용 텍스트로 포맷"""
    lines = []
    total_projects = len(project_info)
    separator = "=" * 80

    for idx, project in enumerate(project_info, start=1):
        lines.append(separator)
        lines.append(f"## [프로젝트 {idx}/{total_projects}] {project['repo_name']}")
        lines.append(separator)
        lines.append(f"- 레포지토리: {project['repo_url']}")

        if project.get("file_tree"):
            tree_summary = ", ".join(project["file_tree"][:10])
            lines.append(f"- 파일 구조: {tree_summary}")

        if project.get("dependencies"):
            lines.append("- 핵심 의존성 [tech_stack에 반드시 포함]:")
            for dep in project["dependencies"][:30]:
                lines.append(f"  * {dep}")

        if project.get("messages"):
            lines.append("- 주요 작업:")
            for msg in project["messages"][:15]:
                lines.append(f"  - {msg}")

        lines.append(separator)
        lines.append("")

    return "\n".join(lines)


def _get_json_schema_prompt(model_class: type) -> str:
    """Pydantic 모델의 JSON 스키마를 프롬프트용 문자열로 변환"""
    schema = model_class.model_json_schema()
    return json.dumps(schema, indent=2, ensure_ascii=False)


async def generate_resume(
    project_info: list[dict],
    position: str,
    repo_urls: list[str],
    feedback: str | None = None,
    repo_contexts: dict[str, RepoContext] | None = None,
    user_stats: UserStats | None = None,
    session_id: str | None = None,
) -> ResumeData:
    """프로젝트 정보 기반 이력서 생성"""
    logger.debug("이력서 생성 요청 position=%s projects=%d", position, len(project_info))

    project_info_text = format_project_info(project_info)
    repo_urls_text = "\n".join(repo_urls)

    if repo_contexts:
        contexts_text = "\n".join(
            f"- {name}: 언어={list(ctx.languages.keys())}, 설명={ctx.description or '없음'}, "
            f"토픽={ctx.topics}"
            + (f"\n  README: {ctx.readme_summary[:500]}..." if ctx.readme_summary else "")
            for name, ctx in repo_contexts.items()
        )
    else:
        contexts_text = "없음"

    if user_stats:
        user_stats_text = (
            f"총 커밋: {user_stats.total_commits}개, "
            f"총 PR: {user_stats.total_prs}개, "
            f"총 이슈: {user_stats.total_issues}개"
        )
    else:
        user_stats_text = "없음"

    if feedback:
        human_content = RESUME_GENERATOR_RETRY_HUMAN.format(
            position=position,
            project_info=project_info_text,
            repo_urls=repo_urls_text,
            feedback=feedback,
            repo_contexts=contexts_text,
            user_stats=user_stats_text,
        )
    else:
        human_content = RESUME_GENERATOR_HUMAN.format(
            position=position,
            project_info=project_info_text,
            repo_urls=repo_urls_text,
            repo_contexts=contexts_text,
            user_stats=user_stats_text,
        )

    json_schema = _get_json_schema_prompt(ResumeData)
    human_content += f"\n\n반드시 다음 JSON 형식으로만 응답하세요:\n```json\n{json_schema}\n```"

    langfuse_handler = get_langfuse_handler(
        session_id=session_id,
        trace_name="resume-generate",
        tags=["resume", "generate", position],
    )
    callbacks = [langfuse_handler] if langfuse_handler else None

    llm = get_llm(settings.llm_generator_model, callbacks).with_structured_output(ResumeData)
    messages = [
        SystemMessage(content=RESUME_GENERATOR_SYSTEM),
        HumanMessage(content=human_content),
    ]
    result = await llm.ainvoke(messages)

    logger.debug("이력서 생성 완료 position=%s", position)
    return result


async def evaluate_resume(
    resume_data: ResumeData, position: str, session_id: str | None = None
) -> EvaluationOutput:
    """이력서 품질 평가"""
    logger.debug("이력서 평가 요청 position=%s", position)

    resume_json = resume_data.model_dump_json(indent=2)

    human_content = RESUME_EVALUATOR_HUMAN.format(
        position=position,
        resume_json=resume_json,
    )

    json_schema = _get_json_schema_prompt(EvaluationOutput)
    human_content += f"\n\n반드시 다음 JSON 형식으로만 응답하세요:\n```json\n{json_schema}\n```"

    langfuse_handler = get_langfuse_handler(
        session_id=session_id,
        trace_name="resume-evaluate",
        tags=["resume", "evaluate", position],
    )
    callbacks = [langfuse_handler] if langfuse_handler else None

    llm = get_llm(settings.llm_evaluator_model, callbacks).with_structured_output(EvaluationOutput)
    messages = [
        SystemMessage(content=RESUME_EVALUATOR_SYSTEM.format(position=position)),
        HumanMessage(content=human_content),
    ]
    result = await llm.ainvoke(messages)

    logger.debug(
        "이력서 평가 완료 result=%s rule=%s item=%s feedback=%s",
        result.result,
        result.violated_rule,
        result.violated_item,
        result.feedback,
    )
    return result
