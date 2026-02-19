import functools
import os

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interview.chat_schemas import ChatOutput
from app.domain.interview.feedback_schemas import (
    FeedbackEvaluationOutput,
    FeedbackOutput,
    OverallFeedbackEvaluationOutput,
    OverallFeedbackOutput,
)
from app.domain.interview.schemas import InterviewEvaluationOutput, InterviewQuestionsOutput
from app.domain.resume.prompts.builder import (
    build_evaluator_system_prompt,
    build_generator_system_prompt,
    format_project_info,
    format_repo_contexts,
)
from app.domain.resume.prompts.positions import get_interview_position_focus
from app.domain.resume.schemas import (
    EvaluationOutput,
    ProjectInfoDict,
    RepoContext,
    ResumeData,
    UserStats,
)
from app.infra.langfuse.prompt_manager import get_prompt

logger = get_logger(__name__)


def setup_langfuse_env() -> None:
    """Langfuse 환경 변수 설정"""
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


@functools.cache
def get_generator_llm() -> ChatOpenAI:
    """이력서 생성용 vLLM 클라이언트 반환"""
    return ChatOpenAI(
        model=settings.vllm_model,
        api_key=settings.vllm_api_key or "EMPTY",
        base_url=settings.vllm_base_url,
        timeout=settings.vllm_timeout,
        temperature=0.1,
        max_tokens=4096,
    )


@functools.cache
def get_evaluator_llm() -> ChatGoogleGenerativeAI:
    """이력서 평가용 Gemini 클라이언트 반환"""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_evaluator_model,
        google_api_key=settings.gemini_api_key,
        timeout=settings.gemini_timeout,
        temperature=0.09,
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
    """구조화된 출력으로 LLM 호출 - 원본 출력 추적 포함"""
    kwargs = {}
    if structured_output_method:
        kwargs["method"] = structured_output_method
    structured_llm = llm.with_structured_output(output_type, include_raw=True, **kwargs)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]
    response = await structured_llm.ainvoke(messages, config=config)

    raw = response.get("raw")
    parsed = response.get("parsed")
    parsing_error = response.get("parsing_error")

    if raw:
        raw_text = raw.content if hasattr(raw, "content") else str(raw)
        logger.debug("LLM 원본 출력", raw_text=raw_text[:500])

    if parsed is not None:
        return parsed

    raw_text = raw.content if raw and hasattr(raw, "content") else "원본 없음"
    logger.error(
        "LLM 출력 파싱 실패",
        raw_text=raw_text[:500],
        output_type=output_type.__name__,
        error=str(parsing_error),
    )
    raise ValueError(f"LLM 출력 파싱 실패: {parsing_error}")


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
    )

    logger.debug("이력서 수정 완료")
    return result


async def evaluate_edited_resume(
    resume_json: str,
    session_id: str | None = None,
) -> EvaluationOutput:
    """수정된 이력서 평가 - Gemini 사용, 포지션 체크 없음"""
    logger.debug("수정 이력서 평가 요청")

    human_content = get_prompt(
        "resume-edit-evaluator-human",
        resume_json=resume_json,
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


async def generate_interview(
    resume_json: str,
    interview_type: str,
    position: str,
    question_count: int,
    feedback: str | None = None,
    session_id: str | None = None,
) -> InterviewQuestionsOutput:
    """면접 질문 생성 - vLLM 사용"""
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


async def generate_chat_response(
    resume_json: str,
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    session_id: str | None = None,
) -> ChatOutput:
    """면접 채팅 응답 생성 - vLLM 사용"""
    logger.debug(
        "채팅 응답 생성 요청",
        interview_type=interview_type,
        position=position,
    )

    related_project_text = related_project or "없음"

    human_content = get_prompt(
        f"chat-{interview_type}-human",
        question_text=question_text,
        question_intent=question_intent,
        related_project=related_project_text,
        answer=answer,
    )

    system_prompt = get_prompt(
        f"chat-{interview_type}-system",
        position=position,
        resume_json=resume_json,
    )
    config = _build_langfuse_config(session_id, ["chat", interview_type, position])

    result = await _invoke_llm(
        llm=get_generator_llm(),
        output_type=ChatOutput,
        system_prompt=system_prompt,
        human_content=human_content,
        config=config,
    )

    logger.debug("채팅 응답 생성 완료")
    return result
