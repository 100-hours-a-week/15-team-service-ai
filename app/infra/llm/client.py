import os

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.resume.prompts import (
    RESUME_EDIT_EVALUATOR_HUMAN,
    RESUME_EDIT_EVALUATOR_SYSTEM,
    RESUME_EDIT_HUMAN,
    RESUME_EDIT_RETRY_HUMAN,
    RESUME_EDIT_SYSTEM,
    RESUME_EVALUATOR_HUMAN,
    RESUME_GENERATOR_HUMAN,
    RESUME_GENERATOR_RETRY_HUMAN,
)
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

logger = get_logger(__name__)


def setup_langfuse_env() -> None:
    """Langfuse 환경 변수 설정 - 앱 시작 시 한 번만 호출"""
    if settings.langfuse_public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    if settings.langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    if settings.langfuse_base_url:
        os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url


def get_langfuse_handler() -> CallbackHandler | None:
    """Langfuse 콜백 핸들러 반환"""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    return CallbackHandler()


def get_generator_llm() -> ChatOpenAI:
    """이력서 생성용 vLLM 클라이언트 반환"""
    return ChatOpenAI(
        model=settings.vllm_model,
        api_key=settings.vllm_api_key or "EMPTY",
        base_url=settings.vllm_base_url,
        timeout=settings.vllm_timeout,
        temperature=0.0,
    )


def get_evaluator_llm() -> ChatGoogleGenerativeAI:
    """이력서 평가용 Gemini 클라이언트 반환"""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_evaluator_model,
        google_api_key=settings.gemini_api_key,
        timeout=settings.gemini_timeout,
        temperature=0.0,
    )


def _build_langfuse_config(session_id: str | None, tags: list[str]) -> dict:
    """Langfuse 콜백 설정 생성"""
    langfuse_handler = get_langfuse_handler()
    return {
        "callbacks": [langfuse_handler] if langfuse_handler else [],
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_tags": tags,
        },
    }


async def _invoke_llm[T](
    llm: BaseChatModel,
    output_type: type[T],
    system_prompt: str,
    human_content: str,
    config: dict,
    structured_output_method: str | None = None,
) -> T:
    """구조화된 출력으로 LLM 호출"""
    kwargs = {}
    if structured_output_method:
        kwargs["method"] = structured_output_method
    llm = llm.with_structured_output(output_type, **kwargs)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]
    return await llm.ainvoke(messages, config=config)


async def generate_resume(
    project_info: list[ProjectInfoDict],
    position: str,
    repo_urls: list[str],
    feedback: str | None = None,
    repo_contexts: dict[str, RepoContext] | None = None,
    user_stats: UserStats | None = None,
    session_id: str | None = None,
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
        human_content = RESUME_GENERATOR_RETRY_HUMAN.format(
            position=position,
            project_info=project_info_text,
            repo_urls=repo_urls_text,
            feedback=feedback,
            repo_contexts=contexts_text,
            user_stats=user_stats_text,
            project_count=project_count,
        )
    else:
        human_content = RESUME_GENERATOR_HUMAN.format(
            position=position,
            project_info=project_info_text,
            repo_urls=repo_urls_text,
            repo_contexts=contexts_text,
            user_stats=user_stats_text,
            project_count=project_count,
        )

    config = _build_langfuse_config(session_id, ["resume", "generate", position])
    system_prompt = build_generator_system_prompt(position)

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=ResumeData,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
    )

    output_count = len(result.projects) if result.projects else 0
    if output_count < project_count:
        logger.warning("프로젝트 누락", input=project_count, output=output_count)

    logger.debug("이력서 생성 완료", position=position, projects=len(result.projects))
    return result


async def evaluate_resume(
    resume_data: ResumeData, position: str, session_id: str | None = None
) -> EvaluationOutput:
    """이력서 품질 평가"""
    logger.debug("이력서 평가 요청", position=position)

    resume_json = resume_data.model_dump_json(indent=2)

    human_content = RESUME_EVALUATOR_HUMAN.format(
        position=position,
        resume_json=resume_json,
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
        human_content = RESUME_EDIT_RETRY_HUMAN.format(
            resume_json=resume_json,
            message=message,
            feedback=feedback,
        )
    else:
        human_content = RESUME_EDIT_HUMAN.format(
            resume_json=resume_json,
            message=message,
        )

    config = _build_langfuse_config(session_id, ["resume", "edit"])

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=output_type,
        system_prompt=RESUME_EDIT_SYSTEM,
        human_content=human_content,
        config=config,
    )

    logger.debug("이력서 수정 완료")
    return result


async def evaluate_edited_resume(
    resume_json: str,
    session_id: str | None = None,
) -> EvaluationOutput:
    """수정된 이력서 평가 - Gemini 사용, 포지션 체크 없음"""
    logger.debug("수정 이력서 평가 요청")

    human_content = RESUME_EDIT_EVALUATOR_HUMAN.format(
        resume_json=resume_json,
    )

    config = _build_langfuse_config(session_id, ["resume", "edit-evaluate"])

    result = await _invoke_llm(
        llm=get_evaluator_llm(),
        output_type=EvaluationOutput,
        system_prompt=RESUME_EDIT_EVALUATOR_SYSTEM,
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
