import httpx
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.interview.feedback_schemas import (
    OverallFeedbackState,
)
from app.domain.resume.error_handler import (
    handle_connection_error,
    handle_data_error,
    handle_http_error,
)
from app.infra.llm.client import (
    generate_overall_feedback,
)

logger = get_logger(__name__)


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
            session_id=state.get("session_id"),
            callbacks=callbacks,
        )

        logger.info(
            "generate_overall_node 완료",
            overall_score=feedback_result.overall_score,
        )

        return {
            **state,
            "feedback_result": feedback_result,
        }

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
