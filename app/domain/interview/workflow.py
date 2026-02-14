import httpx
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.interview.schemas import InterviewState
from app.domain.resume.workflow_utils import (
    evaluate_with_fallback,
    make_should_retry,
    should_evaluate,
)
from app.infra.llm.client import evaluate_interview, generate_interview

logger = get_logger(__name__)

MAX_INTERVIEW_RETRIES = 1


async def generate_node(state: InterviewState) -> InterviewState:
    """면접 질문 생성 노드"""
    retry_count = state.get("retry_count", 0)
    evaluation = state.get("evaluation")

    if evaluation == "fail":
        retry_count += 1
        logger.info("generate_node 재시도", retry_count=retry_count)
    else:
        logger.info("generate_node 시작")

    resume_json = state["resume_json"]
    interview_type = state["interview_type"]
    position = state["position"]
    session_id = state.get("session_id")
    feedback = state.get("evaluation_feedback")

    try:
        questions = await generate_interview(
            resume_json=resume_json,
            interview_type=interview_type,
            position=position,
            feedback=feedback,
            session_id=session_id,
        )

        logger.info("generate_node 완료", questions=len(questions.questions))

        return {
            **state,
            "retry_count": retry_count,
            "questions": questions,
        }

    except httpx.ConnectError:
        logger.error("generate_node LLM 서버 연결 실패")
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.LLM_API_ERROR,
            "error_message": "LLM 서버 연결 실패",
        }

    except httpx.TimeoutException:
        logger.error("generate_node LLM 요청 타임아웃")
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.LLM_API_ERROR,
            "error_message": "LLM 요청 타임아웃",
        }

    except httpx.HTTPStatusError as e:
        logger.error("generate_node LLM API 오류", status=e.response.status_code)
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.LLM_API_ERROR,
            "error_message": f"LLM API 오류: HTTP {e.response.status_code}",
        }

    except (ValueError, KeyError, TypeError) as e:
        logger.error("generate_node 오류", error=str(e), exc_info=True)
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.INTERVIEW_GENERATE_ERROR,
            "error_message": f"면접 질문 생성 실패: {e}",
        }


async def evaluate_node(state: InterviewState) -> InterviewState:
    """면접 질문 평가 노드"""
    questions = state["questions"]
    resume_json = state["resume_json"]
    interview_type = state["interview_type"]
    session_id = state.get("session_id")

    async def _evaluate():
        questions_json = questions.model_dump_json(indent=2)
        return await evaluate_interview(
            questions_json=questions_json,
            resume_json=resume_json,
            interview_type=interview_type,
            session_id=session_id,
        )

    return await evaluate_with_fallback(state, _evaluate)


def create_interview_workflow() -> CompiledStateGraph:
    """면접 질문 생성 워크플로우 생성"""
    workflow = StateGraph(InterviewState)

    workflow.add_node("generate", generate_node)
    workflow.add_node("evaluate", evaluate_node)

    workflow.set_entry_point("generate")

    workflow.add_conditional_edges(
        "generate",
        should_evaluate,
        {
            "evaluate": "evaluate",
            "end": END,
        },
    )

    should_retry = make_should_retry(MAX_INTERVIEW_RETRIES, "generate")
    workflow.add_conditional_edges(
        "evaluate",
        should_retry,
        {
            "generate": "generate",
            "end": END,
        },
    )

    return workflow.compile()
