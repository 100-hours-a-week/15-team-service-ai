"""이력서 수정 LangGraph 워크플로우"""

from typing import Literal

import httpx
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.api.v2.schemas.resume_edit import EditResumeOutput
from app.core.exceptions import ErrorCode
from app.core.logging import get_logger
from app.domain.resume.schemas.edit import EditState
from app.infra.llm.client import edit_resume, evaluate_edited_resume

logger = get_logger(__name__)

MAX_EDIT_RETRIES = 1


async def edit_node(state: EditState) -> EditState:
    """이력서 수정 노드: vLLM으로 이력서 수정"""
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

    except httpx.HTTPStatusError as e:
        logger.error("edit_node LLM API 오류", status=e.response.status_code)
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.LLM_API_ERROR,
            "error_message": f"LLM API 오류: HTTP {e.response.status_code}",
        }

    except (ValueError, KeyError, TypeError) as e:
        logger.error("edit_node 오류", error=str(e), exc_info=True)
        return {
            **state,
            "retry_count": retry_count,
            "error_code": ErrorCode.EDIT_FAILED,
            "error_message": f"이력서 수정 실패: {e}",
        }


async def evaluate_node(state: EditState) -> EditState:
    """수정 평가 노드: Gemini로 품질 평가"""
    logger.info("evaluate_node 시작")

    edited_resume = state["edited_resume"]
    session_id = state.get("session_id")

    try:
        resume_json = edited_resume.model_dump_json(indent=2)
        evaluation = await evaluate_edited_resume(
            resume_json=resume_json,
            session_id=session_id,
        )

        logger.info("evaluate_node 완료", result=evaluation.result)

        return {
            **state,
            "evaluation": evaluation.result,
            "evaluation_feedback": evaluation.feedback,
        }

    except httpx.HTTPStatusError as e:
        logger.warning("evaluate_node LLM API 오류, 평가 건너뜀", status=e.response.status_code)
        return {
            **state,
            "evaluation": "pass",
            "evaluation_feedback": "",
        }

    except (ValueError, KeyError, TypeError) as e:
        logger.warning("evaluate_node 데이터 오류, 평가 건너뜀", error=str(e))
        return {
            **state,
            "evaluation": "pass",
            "evaluation_feedback": "",
        }


def _has_error(state: EditState, caller: str) -> bool:
    """에러 상태 확인"""
    if state.get("error_code"):
        logger.info("에러 발생, 종료", caller=caller)
        return True
    return False


def should_evaluate(state: EditState) -> Literal["evaluate", "end"]:
    """에러 확인: 에러 있으면 종료, 없으면 평가로"""
    return "end" if _has_error(state, "should_evaluate") else "evaluate"


def should_retry(state: EditState) -> Literal["edit", "end"]:
    """재시도 여부 결정"""
    if _has_error(state, "should_retry"):
        return "end"

    evaluation = state.get("evaluation", "pass")
    retry_count = state.get("retry_count", 0)

    if evaluation == "pass":
        logger.info("should_retry: 평가 통과, 종료")
        return "end"

    if retry_count >= MAX_EDIT_RETRIES:
        logger.warning("should_retry: 최대 재시도 도달, 강제 통과")
        return "end"

    logger.info("should_retry: 재시도 필요", retry_count=retry_count)
    return "edit"


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

    workflow.add_conditional_edges(
        "evaluate",
        should_retry,
        {
            "edit": "edit",
            "end": END,
        },
    )

    return workflow.compile()
