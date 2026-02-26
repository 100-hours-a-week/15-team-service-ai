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
from app.infra.llm.client import generate_interview

logger = get_logger(__name__)


async def generate_node(state: InterviewState) -> InterviewState:
    """면접 질문 생성 노드"""
    logger.info("generate_node 시작")

    try:
        questions = await generate_interview(
            resume_json=state["resume_json"],
            interview_type=state["interview_type"],
            position=state["position"],
            question_count=state["question_count"],
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


def create_interview_workflow() -> CompiledStateGraph:
    """면접 질문 생성 워크플로우 생성"""
    workflow = StateGraph(InterviewState)
    workflow.add_node("generate", generate_node)
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", END)
    return workflow.compile()
