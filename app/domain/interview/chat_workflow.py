"""면접 채팅 멀티턴 워크플로우

interrupt + Command 패턴으로 사용자 입력을 기다리며 대화를 이어갑니다
체크포인터가 각 턴의 상태를 저장하므로 같은 thread_id로 호출하면
이전 대화를 기억합니다
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from app.core.logging import get_logger
from app.domain.interview.chat_schemas import (
    MAX_CHAT_TURNS,
    ChatMessage,
    ChatState,
)
from app.infra.llm.client import (
    generate_chat_response,
    generate_chat_response_with_history,
)

logger = get_logger(__name__)


def _format_conversation_history(messages: list[ChatMessage]) -> str:
    """대화 이력을 프롬프트에 넣을 텍스트로 변환"""
    if not messages:
        return "없음"

    lines = []
    for msg in messages:
        role_label = "면접관" if msg["role"] == "ai" else "후보자"
        lines.append(f"{role_label}: {msg['content']}")
    return "\n".join(lines)


async def respond_node(state: ChatState) -> ChatState:
    """LLM을 호출하여 면접관 응답을 생성하는 노드"""
    messages = state.get("messages", [])
    turn_count = state.get("turn_count", 0)
    session_id = state.get("session_id")

    logger.info("respond_node 시작", turn_count=turn_count)

    try:
        if turn_count == 0:
            result = await generate_chat_response(
                resume_json=state["resume_json"],
                position=state["position"],
                interview_type=state["interview_type"],
                question_text=state["question_text"],
                question_intent=state["question_intent"],
                related_project=state.get("related_project"),
                answer=messages[-1]["content"] if messages else "",
                session_id=session_id,
            )
        else:
            conversation_history = _format_conversation_history(messages[:-1])
            latest_answer = messages[-1]["content"] if messages else ""
            result = await generate_chat_response_with_history(
                resume_json=state["resume_json"],
                position=state["position"],
                interview_type=state["interview_type"],
                question_text=state["question_text"],
                question_intent=state["question_intent"],
                related_project=state.get("related_project"),
                answer=latest_answer,
                conversation_history=conversation_history,
                session_id=session_id,
            )

        ai_content = result.message
        if result.follow_up_question:
            ai_content += f"\n\n{result.follow_up_question}"

        ai_message: ChatMessage = {"role": "ai", "content": ai_content}

        logger.info("respond_node 완료", turn_count=turn_count)

        return {
            "messages": [ai_message],
            "last_response": result.message,
            "last_follow_up": result.follow_up_question,
            "turn_count": turn_count + 1,
            "error_message": None,
        }

    except Exception as e:
        logger.error("respond_node 실패", error=str(e), exc_info=True)
        return {
            "error_message": f"채팅 응답 생성 실패: {e}",
            "turn_count": turn_count,
        }


def wait_for_user_node(state: ChatState) -> Command:
    """interrupt로 워크플로우를 일시 정지하고 사용자 입력을 기다리는 노드

    Command(resume=답변_텍스트)로 재개하면
    답변을 Human 메시지로 추가하고 respond_node로 이동합니다
    """
    user_answer = interrupt("사용자 답변을 기다립니다")

    human_message: ChatMessage = {"role": "human", "content": user_answer}

    return Command(
        goto="respond",
        update={"messages": [human_message]},
    )


def _should_continue(state: ChatState) -> str:
    """에러 또는 최대 턴 초과 시 종료, 아니면 사용자 입력 대기"""
    if state.get("error_message"):
        return "end"

    turn_count = state.get("turn_count", 0)
    if turn_count >= MAX_CHAT_TURNS:
        logger.info("최대 채팅 턴 도달", max_turns=MAX_CHAT_TURNS)
        return "end"

    return "wait_for_user"


def create_chat_workflow(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """멀티턴 채팅 워크플로우 생성

    checkpointer가 없으면 interrupt가 동작하지 않습니다
    LangGraph Studio에서 dict를 전달하는 경우 None으로 폴백합니다
    """
    if checkpointer is not None and not isinstance(checkpointer, BaseCheckpointSaver):
        checkpointer = None

    workflow = StateGraph(ChatState)

    workflow.add_node("respond", respond_node)
    workflow.add_node("wait_for_user", wait_for_user_node)

    workflow.set_entry_point("respond")

    workflow.add_conditional_edges(
        "respond",
        _should_continue,
        {
            "wait_for_user": "wait_for_user",
            "end": END,
        },
    )

    return workflow.compile(checkpointer=checkpointer)
