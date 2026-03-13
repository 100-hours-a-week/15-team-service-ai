import httpx
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.interview.schemas import InterviewState
from app.domain.resume.error_handler import (
    handle_connection_error,
    handle_data_error,
    handle_http_error,
)
from app.domain.resume.prompts.positions import get_position_config
from app.infra.llm.client import generate_interview

logger = get_logger(__name__)

REQUIRED_BEHAVIORAL_DIMENSIONS = {"협업", "갈등해결", "성장마인드", "실패경험"}


async def generate_node(state: InterviewState) -> InterviewState:
    """면접 질문 생성 노드"""
    logger.info("generate_node 시작", retry_count=state.get("retry_count", 0))

    feedback = _build_feedback(state) if state.get("retry_count", 0) > 0 else None

    try:
        questions = await generate_interview(
            resume_json=state["resume_json"],
            interview_type=state["interview_type"],
            position=state["position"],
            question_count=state["question_count"],
            min_question_count=state.get("min_question_count", state["question_count"]),
            feedback=feedback,
            session_id=state.get("session_id"),
        )

        logger.info("generate_node 완료", questions=len(questions.questions))

        return {**state, "questions": questions}

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(e, state, "generate_node", ErrorCode.LLM_API_ERROR)

    except httpx.HTTPStatusError as e:
        return handle_http_error(e, state, "generate_node", ErrorCode.LLM_API_ERROR, "LLM API 오류")

    except (ValueError, KeyError, TypeError) as e:
        return handle_data_error(
            e, state, "generate_node", ErrorCode.INTERVIEW_GENERATE_ERROR, "면접 질문 생성 실패"
        )


async def validate_node(state: InterviewState) -> InterviewState:
    """코드 레벨 질문 품질 검증 - latency 0"""
    if state.get("error_code"):
        return {**state, "validation_passed": False}

    questions = state.get("questions")
    if not questions:
        return {**state, "validation_passed": False}

    interview_type = state["interview_type"]

    if interview_type == "behavioral":
        return _validate_behavioral(state, questions)
    return _validate_technical(state, questions)


def _validate_behavioral(state: InterviewState, questions) -> InterviewState:
    """인성 면접 검증: 4개 핵심 dimension 커버 확인"""
    generated_dims = {q.dimension for q in questions.questions if q.dimension}
    missing = REQUIRED_BEHAVIORAL_DIMENSIONS - generated_dims

    if missing:
        logger.warning("dimension 미커버", missing=list(missing))
        return {
            **state,
            "validation_passed": False,
            "missing_dimensions": list(missing),
        }

    logger.info("behavioral validation 통과")
    return {**state, "validation_passed": True}


def _validate_technical(state: InterviewState, questions) -> InterviewState:
    """기술 면접 검증: category 중복 + 허용 목록 확인"""
    categories = [q.category for q in questions.questions if q.category]

    duplicates = [c for c in set(categories) if categories.count(c) > 1]
    if duplicates:
        logger.warning("category 중복", duplicates=duplicates)
        return {
            **state,
            "validation_passed": False,
            "duplicate_categories": duplicates,
        }

    config = get_position_config(state["position"])
    allowed = config.get("technical_categories", [])
    if allowed:
        invalid = [c for c in categories if c not in allowed]
        if invalid:
            logger.warning("허용 외 category", invalid=invalid)
            return {
                **state,
                "validation_passed": False,
                "invalid_categories": invalid,
            }

    logger.info("technical validation 통과")
    return {**state, "validation_passed": True}


def _build_feedback(state: InterviewState) -> str:
    """validate_node 실패 정보를 retry 피드백 문자열로 변환"""
    lines = []

    missing = state.get("missing_dimensions", [])
    if missing:
        lines.append(f"missing_dimensions: {missing}")

    duplicates = state.get("duplicate_categories", [])
    if duplicates:
        lines.append(f"duplicate_categories: {duplicates}")

    invalid = state.get("invalid_categories", [])
    if invalid:
        lines.append(f"invalid_categories: {invalid}")

    return "\n".join(lines) if lines else "이전 생성 결과가 품질 기준을 통과하지 못했습니다"


def should_retry(state: InterviewState) -> str:
    """conditional edge: 검증 결과에 따라 분기"""
    if state.get("validation_passed"):
        return "end"
    if state.get("error_code"):
        return "error"
    if state.get("retry_count", 0) >= 1:
        return "error"
    return "retry"


async def increment_retry(state: InterviewState) -> InterviewState:
    """retry 카운트 증가 노드"""
    return {**state, "retry_count": state.get("retry_count", 0) + 1}


def create_interview_workflow() -> CompiledStateGraph:
    """면접 질문 생성 워크플로우 생성"""
    workflow = StateGraph(InterviewState)

    workflow.add_node("generate", generate_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("increment_retry", increment_retry)

    workflow.set_entry_point("generate")
    workflow.add_edge("generate", "validate")
    workflow.add_conditional_edges(
        "validate",
        should_retry,
        {
            "end": END,
            "error": END,
            "retry": "increment_retry",
        },
    )
    workflow.add_edge("increment_retry", "generate")

    return workflow.compile()
