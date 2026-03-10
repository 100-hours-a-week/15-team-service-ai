import asyncio

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.interview.chat_schemas import ChatMessage, ChatOutput, ChatState
from app.domain.interview.chat_workflow import create_chat_workflow
from app.infra.llm.client import generate_chat_response, get_langfuse_handler

logger = get_logger(__name__)
_chat_workflow: CompiledStateGraph | None = None


async def _run_single_call(
    resume_json: str,
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    session_id: str | None,
) -> tuple[ChatOutput | None, str | None, int]:
    """폴백용 단일 LLM 호출 - 체크포인터 없을 때 사용

    Returns:
        chat_result, error_message, turn_count 튜플
    """
    try:
        result = await asyncio.wait_for(
            generate_chat_response(
                resume_json=resume_json,
                position=position,
                interview_type=interview_type,
                question_text=question_text,
                question_intent=question_intent,
                related_project=related_project,
                answer=answer,
                session_id=session_id,
            ),
            timeout=settings.workflow_timeout,
        )
        return result, None, 1

    except asyncio.TimeoutError:
        logger.error(
            "채팅 응답 타임아웃",
            timeout=settings.workflow_timeout,
        )
        return None, f"채팅 응답 타임아웃: {settings.workflow_timeout}초 초과", 0

    except Exception as e:
        logger.error("채팅 단일 호출 실패", error=str(e), exc_info=True)
        return None, "채팅 응답 생성에 실패했습니다", 0


async def run_chat_agent(
    resume_json: str,
    position: str,
    interview_type: str,
    question_text: str,
    question_intent: str,
    related_project: str | None,
    answer: str,
    session_id: str | None = None,
    thread_id: str | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> tuple[ChatOutput | None, str | None, int]:
    """면접 채팅 에이전트 실행

    체크포인터가 있으면 멀티턴 워크플로우를 사용하고,
    없으면 기존 단일 LLM 호출로 폴백합니다

    Returns:
        chat_result, error_message, turn_count 튜플
    """
    logger.info(
        "채팅 에이전트 시작",
        session_id=session_id,
        thread_id=thread_id,
        has_checkpointer=checkpointer is not None,
    )

    if not checkpointer or not thread_id:
        logger.info("체크포인터 없음 - 단일 호출 폴백")
        return await _run_single_call(
            resume_json=resume_json,
            position=position,
            interview_type=interview_type,
            question_text=question_text,
            question_intent=question_intent,
            related_project=related_project,
            answer=answer,
            session_id=session_id,
        )

    try:
        global _chat_workflow
        if _chat_workflow is None:
            _chat_workflow = create_chat_workflow(checkpointer=checkpointer)
        workflow = _chat_workflow
        langfuse_handler = get_langfuse_handler()
        config = {
            "configurable": {"thread_id": thread_id},
            "callbacks": [langfuse_handler] if langfuse_handler else [],
            "metadata": {
                "langfuse_session_id": session_id,
                "langfuse_tags": ["chat", interview_type, position],
            },
        }

        existing_state = await workflow.aget_state(config)
        is_interrupted = bool(existing_state.next)

        if is_interrupted:
            logger.info("기존 대화 이어서 진행", thread_id=thread_id)
            result_state = await asyncio.wait_for(
                workflow.ainvoke(
                    Command(resume=answer),
                    config=config,
                ),
                timeout=settings.workflow_timeout,
            )
        else:
            logger.info("새 대화 시작", thread_id=thread_id)
            human_message: ChatMessage = {"role": "human", "content": answer}
            initial_state: ChatState = {
                "resume_json": resume_json,
                "position": position,
                "interview_type": interview_type,
                "question_text": question_text,
                "question_intent": question_intent,
                "related_project": related_project,
                "session_id": session_id,
                "messages": [human_message],
                "turn_count": 0,
                "error_message": None,
                "last_response": None,
                "last_follow_up": None,
            }
            result_state = await asyncio.wait_for(
                workflow.ainvoke(initial_state, config=config),
                timeout=settings.workflow_timeout,
            )

        error_message = result_state.get("error_message")
        if error_message:
            logger.error("워크플로우 에러", error=error_message)
            return None, error_message, result_state.get("turn_count", 0)

        turn_count = result_state.get("turn_count", 0)
        chat_output = ChatOutput(
            message=result_state.get("last_response", ""),
            follow_up_question=result_state.get("last_follow_up"),
        )

        logger.info("채팅 에이전트 완료", turn_count=turn_count)
        return chat_output, None, turn_count

    except asyncio.TimeoutError:
        logger.error(
            "채팅 워크플로우 타임아웃",
            timeout=settings.workflow_timeout,
            thread_id=thread_id,
        )
        return None, f"채팅 응답 타임아웃: {settings.workflow_timeout}초 초과", 0

    except Exception as e:
        logger.error("채팅 에이전트 실패", error=str(e), exc_info=True)
        return None, "채팅 응답 생성에 실패했습니다", 0
