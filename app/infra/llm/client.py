from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

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
    ResumeData,
)

logger = get_logger(__name__)


def get_llm():
    """OpenAI LLM 클라이언트 반환."""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout,
    )


async def analyze_diffs_batch(
    diffs: list[str], repo_name: str
) -> list[DiffAnalysisOutput]:
    """여러 diff를 한 번에 분석하여 경험 추출.

    Args:
        diffs: diff 내용 리스트
        repo_name: 레포지토리 이름

    Returns:
        추출된 경험 목록
    """
    logger.info("diff 배치 분석 요청 repo=%s count=%d", repo_name, len(diffs))

    diffs_content = "\n\n---\n\n".join(
        f"[커밋 {i + 1}]\n{diff}" for i, diff in enumerate(diffs)
    )

    llm = get_llm().with_structured_output(DiffBatchOutput)
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
    logger.info(
        "diff 배치 분석 완료 repo=%s experiences=%d", repo_name, len(result.experiences)
    )
    return result.experiences


async def generate_resume(
    experiences: list[DiffAnalysisOutput],
    position: str,
    repo_urls: list[str],
    feedback: str | None = None,
) -> ResumeData:
    """경험 기반 이력서 생성.

    Args:
        experiences: 분석된 경험 목록
        position: 희망 포지션
        repo_urls: 레포지토리 URL 목록
        feedback: 이전 평가 피드백 (재시도 시)

    Returns:
        생성된 이력서 데이터
    """
    logger.info("이력서 생성 요청 position=%s", position)

    experiences_text = "\n".join(
        f"- 기술: {exp.tech_stack}, 내용: {exp.description}" for exp in experiences
    )
    repo_urls_text = "\n".join(repo_urls)

    if feedback:
        human_content = RESUME_GENERATOR_RETRY_HUMAN.format(
            position=position,
            experiences_text=experiences_text,
            repo_urls=repo_urls_text,
            feedback=feedback,
        )
    else:
        human_content = RESUME_GENERATOR_HUMAN.format(
            position=position,
            experiences_text=experiences_text,
            repo_urls=repo_urls_text,
        )

    llm = get_llm().with_structured_output(ResumeData)
    messages = [
        SystemMessage(content=RESUME_GENERATOR_SYSTEM),
        HumanMessage(content=human_content),
    ]

    result = await llm.ainvoke(messages)
    logger.info("이력서 생성 완료 position=%s", position)
    return result


async def evaluate_resume(resume_data: ResumeData, position: str) -> EvaluationOutput:
    """이력서 품질 평가.

    Args:
        resume_data: 생성된 이력서
        position: 희망 포지션

    Returns:
        평가 결과 (pass/fail + 피드백)
    """
    logger.info("이력서 평가 요청 position=%s", position)

    resume_json = resume_data.model_dump_json(indent=2)

    llm = get_llm().with_structured_output(EvaluationOutput)
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
    logger.info("이력서 평가 완료 result=%s", result.result)
    return result
