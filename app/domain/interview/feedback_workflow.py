import asyncio

import httpx
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.config import settings
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.interview.feedback_schemas import (
    FeedbackState,
    OverallFeedbackState,
)
from app.domain.resume.error_handler import (
    handle_connection_error,
    handle_data_error,
    handle_http_error,
)
from app.infra.llm.client import (
    evaluate_retrieval_quality,
    generate_feedback,
    generate_overall_feedback,
)
from app.infra.qdrant.client import search_knowledge

logger = get_logger(__name__)


async def retrieve_node(state: FeedbackState) -> dict:
    """Qdrant 검색 노드 - 기술 면접만 적용, 포지션 카테고리 필터링"""
    if state.get("interview_type") != "technical":
        return {"retrieved_context": "", "retrieval_scores": [], "retrieval_attempt": 0}

    intent = state.get("question_intent", "")
    position = state.get("position", "")
    query = f"{state['question_text']} {intent}".strip()
    chunks = await asyncio.to_thread(search_knowledge, query, None, position)

    scores = [c["score"] for c in chunks]
    retrieved_context = ""
    if chunks:
        retrieved_context = "\n\n".join(
            f"[{c['tech']} - {c['topic']}] {c['document']}" for c in chunks
        )
    return {
        "retrieved_context": retrieved_context,
        "retrieval_scores": scores,
        "retrieval_attempt": 0,
    }


def should_retry_retrieval(state: FeedbackState) -> str:
    """검색 점수 기반 재검색 여부 결정"""
    if state.get("interview_type") != "technical":
        return "generate"

    scores = state.get("retrieval_scores", [])
    if scores and max(scores) >= settings.qdrant_score_threshold:
        return "generate"

    logger.info(
        "검색 품질 낮음 - 재검색 결정",
        max_score=max(scores) if scores else 0.0,
        threshold=settings.qdrant_score_threshold,
    )
    return "re_retrieve"


async def re_retrieve_node(state: FeedbackState) -> dict:
    """재검색 노드 - 포지션+질문+의도로 쿼리 확장, 카테고리 필터링 유지"""
    position = state.get("position", "")
    intent = state.get("question_intent", "")
    query = f"{position} {state['question_text']} {intent}".strip()

    chunks = await asyncio.to_thread(search_knowledge, query, settings.qdrant_top_k_retry, position)

    scores = [c["score"] for c in chunks]
    min_score = settings.qdrant_score_threshold
    retrieved_context = ""
    if scores and max(scores) >= min_score:
        filtered = [c for c in chunks if c["score"] >= min_score * 0.8]
        retrieved_context = "\n\n".join(
            f"[{c['tech']} - {c['topic']}] {c['document']}" for c in filtered
        )
    else:
        logger.info(
            "재검색 후에도 품질 미달 - context 주입 안 함",
            max_score=max(scores) if scores else 0.0,
            threshold=min_score,
        )

    original_scores = state.get("retrieval_scores", [])
    logger.info(
        "재검색 완료",
        original_max_score=max(original_scores) if original_scores else 0.0,
        retry_max_score=max(scores) if scores else 0.0,
        top_k=settings.qdrant_top_k_retry,
    )
    return {
        "retrieved_context": retrieved_context,
        "retrieval_scores": scores,
        "retrieval_attempt": 1,
    }


async def post_retrieval_node(state: FeedbackState) -> dict:
    """retrieval 완료 후 병렬 분기 진입점 - evaluate_retrieval + generate를 동시 실행"""
    return {}


async def evaluate_retrieval_node(
    state: FeedbackState,
    config: RunnableConfig,
) -> dict:
    """Retrieval 품질 평가 노드 - 로깅 전용, 워크플로우 영향 없음"""
    if state.get("interview_type") != "technical":
        return {}

    retrieved_context = state.get("retrieved_context", "")
    if not retrieved_context:
        return {}

    callbacks = config.get("callbacks", [])
    try:
        eval_result = await evaluate_retrieval_quality(
            question_text=state["question_text"],
            question_intent=state.get("question_intent", ""),
            retrieved_context=retrieved_context,
            session_id=state.get("session_id"),
            callbacks=callbacks,
        )
        logger.info(
            "retrieval 품질 평가 완료",
            result=eval_result.result,
            reason=eval_result.reason,
            retrieval_attempt=state.get("retrieval_attempt", 0),
            max_score=max(state.get("retrieval_scores", []) or [0.0]),
        )
        return {"retrieval_eval_result": eval_result.result}
    except Exception as e:
        logger.warning("retrieval 품질 평가 실패 - 무시", error=str(e))
        return {}


async def generate_node(
    state: FeedbackState,
    config: RunnableConfig,
) -> FeedbackState:
    """개별 피드백 생성 노드"""
    callbacks = config.get("callbacks", [])

    try:
        feedback_result = await generate_feedback(
            position=state["position"],
            interview_type=state["interview_type"],
            question_text=state["question_text"],
            question_intent=state["question_intent"],
            related_project=state.get("related_project"),
            answer=state["answer"],
            retrieved_context=state.get("retrieved_context", ""),
            session_id=state.get("session_id"),
            callbacks=callbacks,
        )
        return {"feedback_result": feedback_result}

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(e, state, "generate_node", ErrorCode.LLM_API_ERROR)

    except httpx.HTTPStatusError as e:
        return handle_http_error(e, state, "generate_node", ErrorCode.LLM_API_ERROR, "LLM API 오류")

    except (ValueError, KeyError, TypeError) as e:
        return handle_data_error(
            e, state, "generate_node", ErrorCode.FEEDBACK_GENERATE_ERROR, "피드백 생성 실패"
        )


def create_feedback_workflow() -> CompiledStateGraph:
    """개별 피드백 워크플로우 - retrieve → [재검색 조건] → evaluate_retrieval || generate"""
    workflow = StateGraph(FeedbackState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("re_retrieve", re_retrieve_node)
    workflow.add_node("post_retrieval", post_retrieval_node)
    workflow.add_node("evaluate_retrieval", evaluate_retrieval_node)
    workflow.add_node("generate", generate_node)
    workflow.set_entry_point("retrieve")
    workflow.add_conditional_edges(
        "retrieve",
        should_retry_retrieval,
        {"generate": "post_retrieval", "re_retrieve": "re_retrieve"},
    )
    workflow.add_edge("re_retrieve", "post_retrieval")
    workflow.add_edge("post_retrieval", "evaluate_retrieval")
    workflow.add_edge("post_retrieval", "generate")
    workflow.add_edge("evaluate_retrieval", END)
    workflow.add_edge("generate", END)
    return workflow.compile()


async def generate_overall_node(
    state: OverallFeedbackState,
    config: RunnableConfig,
) -> OverallFeedbackState:
    """종합 피드백 생성 노드"""
    callbacks = config.get("callbacks", [])
    logger.info("generate_overall_node 시작")

    try:
        feedback_result = await generate_overall_feedback(
            position=state["position"],
            interview_type=state["interview_type"],
            qa_pairs_json=state["qa_pairs_json"],
            individual_feedbacks_json=state.get("individual_feedbacks_json", ""),
            company=state.get("company", ""),
            company_talent_info=state.get("company_talent_info", ""),
            session_id=state.get("session_id"),
            callbacks=callbacks,
        )

        logger.info(
            "generate_overall_node 완료",
            overall_score=feedback_result.overall_score,
        )

        return {"feedback_result": feedback_result}

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(
            e,
            state,
            "generate_overall_node",
            ErrorCode.LLM_API_ERROR,
        )

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e,
            state,
            "generate_overall_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
        )

    except (ValueError, KeyError, TypeError) as e:
        return handle_data_error(
            e,
            state,
            "generate_overall_node",
            ErrorCode.FEEDBACK_GENERATE_ERROR,
            "종합 피드백 생성 실패",
        )


def create_overall_feedback_workflow() -> CompiledStateGraph:
    """종합 피드백 워크플로우 생성 - 단일 생성 노드"""
    workflow = StateGraph(OverallFeedbackState)
    workflow.add_node("generate", generate_overall_node)
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", END)
    return workflow.compile()
