import json

import httpx
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.exceptions import ErrorCode, LLMError
from app.core.logging import get_logger
from app.domain.resume.error_handler import (
    handle_connection_error,
    handle_data_error,
    handle_http_error,
)
from app.domain.resume.schemas.edit import ClassifyOutput, EditResumeOutput, EditState
from app.domain.resume.workflow_utils import (
    evaluate_with_fallback,
    make_should_retry,
    should_evaluate,
)
from app.infra.llm.client import classify_edit, edit_resume, evaluate_edited_resume, plan_edit

logger = get_logger(__name__)

MAX_EDIT_RETRIES = 1


async def classify_node(state: EditState) -> EditState:
    """분류 노드 - Gemini가 사용자 요청을 분류하여 범위 밖 요청 식별"""
    logger.info("classify_node 시작")

    resume_json = state["resume_json"]
    message = state["message"]
    session_id = state.get("session_id")

    try:
        classification = await classify_edit(
            resume_json=resume_json,
            message=message,
            session_id=session_id,
        )

        logger.info(
            "classify_node 완료",
            category=classification.intent_category,
            confidence=classification.confidence,
        )

        return {**state, "classification": classification}

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning("classify_node 연결 실패, 기본 edit 경로로 폴백")
        return state

    except httpx.HTTPStatusError:
        logger.warning("classify_node API 오류, 기본 edit 경로로 폴백")
        return state

    except (ValueError, KeyError, TypeError, LLMError):
        logger.warning("classify_node 데이터 오류, 기본 edit 경로로 폴백")
        return state


async def reject_node(state: EditState) -> EditState:
    """거절 노드 - 범위 밖 요청 즉시 거절"""
    classification: ClassifyOutput = state["classification"]
    logger.info("reject_node 실행", reason=classification.reason)

    return {
        **state,
        "error_code": ErrorCode.EDIT_OUT_OF_SCOPE,
        "error_message": classification.reason,
        "reject_reason": classification.reason,
    }


def should_classify(state: EditState) -> str:
    """분류 결과에 따라 edit 또는 reject으로 분기"""
    classification = state.get("classification")

    if classification is None:
        logger.info("should_classify: classification 없음, edit으로 진행")
        return "edit"

    if classification.intent_category == "out_of_scope":
        logger.info("should_classify: out_of_scope, reject으로 진행")
        return "reject"

    logger.info(
        "should_classify: 유효한 수정 요청, edit으로 진행",
        category=classification.intent_category,
    )
    return "edit"


async def plan_node(state: EditState) -> EditState:
    """수정 계획 노드 - Gemini가 사용자 요청을 분석하여 vLLM향 수정 지시를 생성"""
    logger.info("plan_node 시작")

    resume_json = state["resume_json"]
    message = state["message"]
    session_id = state.get("session_id")

    try:
        edit_plan = await plan_edit(
            resume_json=resume_json,
            message=message,
            session_id=session_id,
        )

        logger.info(
            "plan_node 완료",
            edit_type=edit_plan.edit_type,
            target=edit_plan.target_summary,
        )

        return {**state, "edit_plan": edit_plan}

    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return handle_connection_error(
            e,
            state,
            "plan_node",
            ErrorCode.LLM_API_ERROR,
        )

    except httpx.HTTPStatusError as e:
        return handle_http_error(
            e,
            state,
            "plan_node",
            ErrorCode.LLM_API_ERROR,
            "LLM API 오류",
        )

    except (ValueError, KeyError, TypeError, LLMError) as e:
        return handle_data_error(
            e,
            state,
            "plan_node",
            ErrorCode.EDIT_FAILED,
            "수정 계획 생성 실패",
        )


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
    edit_plan = state.get("edit_plan")
    classification = state.get("classification")

    effective_message = message
    if edit_plan is not None:
        effective_message = (
            f"{message}\n\n"
            f"[수정 계획]\n"
            f"유형: {edit_plan.edit_type}\n"
            f"대상: {edit_plan.target_summary}\n"
            f"지시: {edit_plan.detailed_instructions}"
        )
    elif classification is not None:
        effective_message = (
            f"{message}\n\n"
            f"[분류 결과]\n"
            f"유형: {classification.intent_category}\n"
            f"사유: {classification.reason}"
        )

    try:
        edited_resume = await edit_resume(
            resume_json=resume_json,
            message=effective_message,
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

    except (ValueError, KeyError, TypeError, LLMError) as e:
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
        edited = json.loads(edited_resume.model_dump_json())
        return original == edited
    except (json.JSONDecodeError, Exception):
        return False


async def evaluate_node(state: EditState) -> EditState:
    """수정 평가 노드"""
    edited_resume = state["edited_resume"]
    session_id = state.get("session_id")

    if _is_resume_unchanged(state["resume_json"], edited_resume):
        user_message = state.get("message", "")
        logger.warning("수정 전후 이력서 동일")
        return {
            **state,
            "evaluation": "fail",
            "evaluation_feedback": (
                f"수정 사항이 감지되지 않았습니다. "
                f"사용자 요청: '{user_message}' - 이 요청을 반드시 이력서에 반영하세요. "
                f"질문형 표현도 수정 요청입니다. "
                f"tech_stack과 description 모든 필드에서 관련 내용을 찾아 변경하세요."
            ),
        }

    user_message = state.get("message", "")

    async def _evaluate():
        resume_json = edited_resume.model_dump_json(indent=2)
        return await evaluate_edited_resume(
            resume_json=resume_json,
            session_id=session_id,
            user_message=user_message,
        )

    return await evaluate_with_fallback(state, _evaluate)


def _should_continue_after_plan(state: EditState) -> str:
    return "end" if state.get("error_code") else "edit"


def create_edit_workflow() -> CompiledStateGraph:
    """이력서 수정 워크플로우 생성

    워크플로우: classify → [plan → edit | reject] → evaluate → retry/END
    """
    workflow = StateGraph(EditState)

    workflow.add_node("classify", classify_node)
    workflow.add_node("reject", reject_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("edit", edit_node)
    workflow.add_node("evaluate", evaluate_node)

    workflow.set_entry_point("classify")

    workflow.add_conditional_edges(
        "classify",
        should_classify,
        {
            "edit": "plan",
            "reject": "reject",
        },
    )

    workflow.add_edge("reject", END)
    workflow.add_conditional_edges(
        "plan",
        _should_continue_after_plan,
        {"edit": "edit", "end": END},
    )

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
