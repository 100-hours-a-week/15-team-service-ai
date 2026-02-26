import httpx
from langgraph.graph.state import CompiledStateGraph

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
from app.domain.resume.workflow_utils import (
    build_gen_eval_retry_graph,
    evaluate_with_fallback,
)
from app.infra.llm.client import (
    evaluate_feedback,
    evaluate_overall_feedback,
    generate_feedback,
    generate_overall_feedback,
)

logger = get_logger(__name__)

MAX_FEEDBACK_RETRIES = 1


async def generate_feedback_node(state: FeedbackState) -> FeedbackState:
    """개별 피드백 생성 노드"""
    retry_count = state.get("retry_count", 0)
    evaluation = state.get("evaluation")

    if evaluation == "fail":
        retry_count += 1
        logger.info("generate_feedback_node 재시도", retry_count=retry_count)
    else:
        logger.info("generate_feedback_node 시작")

    try:
        feedback_result = await generate_feedback(
            resume_json=state["resume_json"],
            position=state["position"],
            interview_type=state["interview_type"],
            question_text=state["question_text"],
            question_intent=state["question_intent"],
            related_project=state.get("related_project"),
            answer=state["answer"],
            feedback=state.get("evaluation_feedback"),
            session_id=state.get("session_id"),
        )

        logger.info("generate_feedback_node 완료", score=feedback_result.score)

        return {
            **state,
            "retry_count": retry_count,
            "feedback_result": feedback_result,
        }

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(
            e,
            state,
            "generate_feedback_node",
            ErrorCode.LLM_API_ERROR,
            retry_count=retry_count,
        )

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e,
            state,
            "generate_feedback_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
            retry_count=retry_count,
        )

    except (ValueError, KeyError, TypeError) as e:
        return handle_data_error(
            e,
            state,
            "generate_feedback_node",
            ErrorCode.FEEDBACK_GENERATE_ERROR,
            "피드백 생성 실패",
            retry_count=retry_count,
        )


async def evaluate_feedback_node(state: FeedbackState) -> FeedbackState:
    """개별 피드백 평가 노드"""
    feedback_result = state["feedback_result"]
    session_id = state.get("session_id")

    async def _evaluate():
        feedback_json = feedback_result.model_dump_json(indent=2)
        return await evaluate_feedback(
            feedback_json=feedback_json,
            question_text=state["question_text"],
            answer=state["answer"],
            interview_type=state["interview_type"],
            session_id=session_id,
        )

    return await evaluate_with_fallback(state, _evaluate)


async def generate_overall_node(
    state: OverallFeedbackState,
) -> OverallFeedbackState:
    """종합 피드백 생성 노드"""
    retry_count = state.get("retry_count", 0)
    evaluation = state.get("evaluation")

    if evaluation == "fail":
        retry_count += 1
        logger.info("generate_overall_node 재시도", retry_count=retry_count)
    else:
        logger.info("generate_overall_node 시작")

    try:
        feedback_result = await generate_overall_feedback(
            resume_json=state["resume_json"],
            position=state["position"],
            interview_type=state["interview_type"],
            qa_pairs_json=state["qa_pairs_json"],
            feedback=state.get("evaluation_feedback"),
            session_id=state.get("session_id"),
        )

        logger.info(
            "generate_overall_node 완료",
            overall_score=feedback_result.overall_score,
        )

        return {
            **state,
            "retry_count": retry_count,
            "feedback_result": feedback_result,
        }

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(
            e,
            state,
            "generate_overall_node",
            ErrorCode.LLM_API_ERROR,
            retry_count=retry_count,
        )

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e,
            state,
            "generate_overall_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
            retry_count=retry_count,
        )

    except (ValueError, KeyError, TypeError) as e:
        return handle_data_error(
            e,
            state,
            "generate_overall_node",
            ErrorCode.FEEDBACK_GENERATE_ERROR,
            "종합 피드백 생성 실패",
            retry_count=retry_count,
        )


async def evaluate_overall_node(
    state: OverallFeedbackState,
) -> OverallFeedbackState:
    """종합 피드백 평가 노드"""
    feedback_result = state["feedback_result"]
    session_id = state.get("session_id")

    async def _evaluate():
        overall_feedback_json = feedback_result.model_dump_json(indent=2)
        return await evaluate_overall_feedback(
            overall_feedback_json=overall_feedback_json,
            qa_pairs_json=state["qa_pairs_json"],
            interview_type=state["interview_type"],
            session_id=session_id,
        )

    return await evaluate_with_fallback(state, _evaluate)


def create_feedback_workflow() -> CompiledStateGraph:
    """개별 피드백 워크플로우 생성"""
    return build_gen_eval_retry_graph(
        state_schema=FeedbackState,
        generate_node=generate_feedback_node,
        evaluate_node=evaluate_feedback_node,
        max_retries=MAX_FEEDBACK_RETRIES,
    )


def create_overall_feedback_workflow() -> CompiledStateGraph:
    """종합 피드백 워크플로우 생성"""
    return build_gen_eval_retry_graph(
        state_schema=OverallFeedbackState,
        generate_node=generate_overall_node,
        evaluate_node=evaluate_overall_node,
        max_retries=MAX_FEEDBACK_RETRIES,
    )
