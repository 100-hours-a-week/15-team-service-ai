import json

import httpx
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.resume.error_handler import (
    handle_connection_error,
    handle_data_error,
    handle_http_error,
)
from app.domain.resume.schemas.edit import EditResumeOutput, EditState
from app.domain.resume.workflow_utils import (
    evaluate_with_fallback,
    make_should_retry,
    should_evaluate,
)
from app.infra.llm.client import edit_resume, evaluate_edited_resume

logger = get_logger(__name__)

MAX_EDIT_RETRIES = 1


async def edit_node(state: EditState) -> EditState:
    """이력서 수정 노드"""
    retry_count = state.get("retry_count", 0)
    evaluation = state.get("evaluation")

    if evaluation == "fail":
        retry_count += 1
        logger.info("edit_node 재시도", retry_count=retry_count)
    else:
        logger.info("edit_node 시작")

    resume_json = state["resume_json"]
    message = state["message"]
    session_id = state.get("session_id")
    feedback = state.get("evaluation_feedback")

    try:
        edited_resume = await edit_resume(
            resume_json=resume_json,
            message=message,
            output_type=EditResumeOutput,
            feedback=feedback,
            session_id=session_id,
        )

        logger.info("edit_node 완료", projects=len(edited_resume.projects))

        return {
            **state,
            "retry_count": retry_count,
            "edited_resume": edited_resume,
        }

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(
            e,
            state,
            "edit_node",
            ErrorCode.LLM_API_ERROR,
            retry_count=retry_count,
        )

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e,
            state,
            "edit_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
            retry_count=retry_count,
        )

    except (ValueError, KeyError, TypeError) as e:
        return handle_data_error(
            e,
            state,
            "edit_node",
            ErrorCode.EDIT_FAILED,
            "이력서 수정 실패",
            retry_count=retry_count,
        )


def _is_resume_unchanged(original_json: str, edited_resume: EditResumeOutput) -> bool:
    """수정 전후 이력서 비교 - projects만 비교"""
    try:
        original = json.loads(original_json)
        edited = json.loads(edited_resume.model_dump_json(exclude={"message"}))
        return original == edited
    except (json.JSONDecodeError, Exception):
        return False


async def evaluate_node(state: EditState) -> EditState:
    """수정 평가 노드"""
    edited_resume = state["edited_resume"]
    session_id = state.get("session_id")

    if _is_resume_unchanged(state["resume_json"], edited_resume):
        logger.warning("수정 전후 이력서 동일")
        return {
            **state,
            "evaluation": "fail",
            "evaluation_feedback": "수정 사항이 감지되지 않았습니다. "
            "사용자의 요청을 다시 분석하고 반드시 변경을 수행하세요",
        }

    async def _evaluate():
        resume_json = edited_resume.model_dump_json(indent=2)
        return await evaluate_edited_resume(
            resume_json=resume_json,
            session_id=session_id,
        )

    return await evaluate_with_fallback(state, _evaluate)


def create_edit_workflow() -> CompiledStateGraph:
    """이력서 수정 워크플로우 생성"""
    workflow = StateGraph(EditState)

    workflow.add_node("edit", edit_node)
    workflow.add_node("evaluate", evaluate_node)

    workflow.set_entry_point("edit")

    workflow.add_conditional_edges(
        "edit",
        should_evaluate,
        {
            "evaluate": "evaluate",
            "end": END,
        },
    )

    should_retry = make_should_retry(MAX_EDIT_RETRIES, "edit")
    workflow.add_conditional_edges(
        "evaluate",
        should_retry,
        {
            "edit": "edit",
            "end": END,
        },
    )

    return workflow.compile()
