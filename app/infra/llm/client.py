import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.resume.prompts import (
    DIFF_ANALYSIS_HUMAN,
    DIFF_ANALYSIS_SYSTEM,
    RESUME_EVALUATOR_HUMAN,
    RESUME_EVALUATOR_SYSTEM,
    RESUME_GENERATOR_HUMAN,
    RESUME_GENERATOR_RETRY_HUMAN,
    RESUME_GENERATOR_SYSTEM,
)
from app.domain.resume.schemas import (
    DiffAnalysisOutput,
    DiffBatchOutput,
    EvaluationOutput,
    RepoContext,
    ResumeData,
)

logger = get_logger(__name__)

if settings.langfuse_public_key:
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
if settings.langfuse_secret_key:
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
if settings.langfuse_base_url:
    os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url


def get_langfuse_handler(session_id: str | None = None) -> CallbackHandler | None:
    """Langfuse 콜백 핸들러 반환. 설정되지 않으면 None."""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    return CallbackHandler()


def get_llm(callbacks: list | None = None):
    """OpenAI LLM 클라이언트 반환."""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout,
        callbacks=callbacks,
    )


async def analyze_diffs_batch(
    diffs: list[str], repo_name: str, session_id: str | None = None
) -> list[DiffAnalysisOutput]:
    """여러 diff를 한 번에 분석하여 경험 추출.

    Args:
        diffs: diff 내용 리스트
        repo_name: 레포지토리 이름
        session_id: Langfuse 세션 ID

    Returns:
        추출된 경험 목록
    """
    logger.info("diff 배치 분석 요청 repo=%s count=%d", repo_name, len(diffs))

    diffs_content = "\n\n---\n\n".join(f"[커밋 {i + 1}]\n{diff}" for i, diff in enumerate(diffs))
    logger.info("diffs_content 크기 repo=%s chars=%d", repo_name, len(diffs_content))

    langfuse_handler = get_langfuse_handler(session_id)
    callbacks = [langfuse_handler] if langfuse_handler else None

    llm = get_llm(callbacks).with_structured_output(DiffBatchOutput)
    messages = [
        SystemMessage(content=DIFF_ANALYSIS_SYSTEM),
        HumanMessage(
            content=DIFF_ANALYSIS_HUMAN.format(
                repo_name=repo_name,
                diffs_content=diffs_content,
            )
        ),
    ]

    result = await llm.ainvoke(messages)
    logger.info("diff 배치 분석 완료 repo=%s experiences=%d", repo_name, len(result.experiences))
    return result.experiences


async def generate_resume(
    experiences: list[DiffAnalysisOutput],
    position: str,
    repo_urls: list[str],
    feedback: str | None = None,
    repo_contexts: dict[str, RepoContext] | None = None,
    session_id: str | None = None,
) -> ResumeData:
    """경험 기반 이력서 생성.

    Args:
        experiences: 분석된 경험 목록
        position: 희망 포지션
        repo_urls: 레포지토리 URL 목록
        feedback: 이전 평가 피드백, 재시도 시 사용
        repo_contexts: 레포지토리 컨텍스트 정보
        session_id: Langfuse 세션 ID

    Returns:
        생성된 이력서 데이터
    """
    logger.info("이력서 생성 요청 position=%s", position)

    experiences_text = "\n".join(
        f"- 기술: {exp.tech_stack}, 내용: {exp.description}" for exp in experiences
    )
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

    if feedback:
        human_content = RESUME_GENERATOR_RETRY_HUMAN.format(
            position=position,
            experiences_text=experiences_text,
            repo_urls=repo_urls_text,
            feedback=feedback,
            repo_contexts=contexts_text,
        )
    else:
        human_content = RESUME_GENERATOR_HUMAN.format(
            position=position,
            experiences_text=experiences_text,
            repo_urls=repo_urls_text,
            repo_contexts=contexts_text,
        )

    langfuse_handler = get_langfuse_handler(session_id)
    callbacks = [langfuse_handler] if langfuse_handler else None

    llm = get_llm(callbacks).with_structured_output(ResumeData)
    messages = [
        SystemMessage(content=RESUME_GENERATOR_SYSTEM),
        HumanMessage(content=human_content),
    ]

    result = await llm.ainvoke(messages)
    logger.info("이력서 생성 완료 position=%s", position)
    return result


async def evaluate_resume(
    resume_data: ResumeData, position: str, session_id: str | None = None
) -> EvaluationOutput:
    """이력서 품질 평가.

    Args:
        resume_data: 생성된 이력서
        position: 희망 포지션
        session_id: Langfuse 세션 ID

    Returns:
        평가 결과 (pass/fail + 피드백)
    """
    logger.info("이력서 평가 요청 position=%s", position)

    resume_json = resume_data.model_dump_json(indent=2)

    langfuse_handler = get_langfuse_handler(session_id)
    callbacks = [langfuse_handler] if langfuse_handler else None

    llm = get_llm(callbacks).with_structured_output(EvaluationOutput)
    messages = [
        SystemMessage(content=RESUME_EVALUATOR_SYSTEM.format(position=position)),
        HumanMessage(
            content=RESUME_EVALUATOR_HUMAN.format(
                position=position,
                resume_json=resume_json,
            )
        ),
    ]

    result = await llm.ainvoke(messages)
    logger.info("이력서 평가 완료 result=%s feedback=%s", result.result, result.feedback)
    return result
