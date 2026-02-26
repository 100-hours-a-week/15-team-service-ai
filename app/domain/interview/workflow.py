import httpx
from langgraph.graph.state import CompiledStateGraph

from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.interview.schemas import InterviewState
from app.domain.resume.error_handler import (
    handle_connection_error,
    handle_data_error,
    handle_http_error,
)
from app.domain.resume.workflow_utils import (
    build_gen_eval_retry_graph,
    evaluate_with_fallback,
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
    question_count = state["question_count"]

    try:
        questions = await generate_interview(
            resume_json=resume_json,
            interview_type=interview_type,
            position=position,
            question_count=question_count,
            feedback=feedback,
            session_id=session_id,
        )

        logger.info("generate_node 완료", questions=len(questions.questions))

        return {
            **state,
            "retry_count": retry_count,
            "questions": questions,
        }

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(
            e,
            state,
            "generate_node",
            ErrorCode.LLM_API_ERROR,
            retry_count=retry_count,
        )

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e,
            state,
            "generate_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
            retry_count=retry_count,
        )

    except (ValueError, KeyError, TypeError) as e:
        return handle_data_error(
            e,
            state,
            "generate_node",
            ErrorCode.INTERVIEW_GENERATE_ERROR,
            "면접 질문 생성 실패",
            retry_count=retry_count,
        )


async def evaluate_node(state: InterviewState) -> InterviewState:
    """면접 질문 평가 노드"""
    questions = state["questions"]
    resume_json = state["resume_json"]
    interview_type = state["interview_type"]
    question_count = state["question_count"]
    session_id = state.get("session_id")

    async def _evaluate():
        questions_json = questions.model_dump_json(indent=2)
        return await evaluate_interview(
            questions_json=questions_json,
            resume_json=resume_json,
            interview_type=interview_type,
            question_count=question_count,
            session_id=session_id,
        )

    return await evaluate_with_fallback(state, _evaluate)


def create_interview_workflow() -> CompiledStateGraph:
    """면접 질문 생성 워크플로우 생성"""
    return build_gen_eval_retry_graph(
        state_schema=InterviewState,
        generate_node=generate_node,
        evaluate_node=evaluate_node,
        max_retries=MAX_INTERVIEW_RETRIES,
    )
