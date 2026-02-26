import asyncio
from unittest.mock import AsyncMock, patch

from app.domain.interview.chat_schemas import ChatOutput
from app.domain.interview.store import (
    InterviewContextStore,
    QuestionContext,
    SessionMeta,
)

SAMPLE_CHAT_OUTPUT = ChatOutput(
    message="좋은 답변입니다",
    follow_up_question="그렇다면 성능 최적화는 어떻게 했나요?",
)

SAMPLE_CHAT_REQUEST = {
    "aiSessionId": "test-session-001",
    "questionId": "q-test-001",
    "answer": "FastAPI에서 async/await을 사용하여 비동기 처리를 구현했습니다",
}


def _setup_store(store: InterviewContextStore) -> None:
    """테스트용 스토어에 샘플 데이터 저장"""
    store.save(
        session_id="test-session-001",
        contexts=[
            QuestionContext(
                question_id="q-test-001",
                question_text="비동기 처리의 장점은?",
                intent="비동기 프로그래밍 이해도",
                related_project="test-project",
            ),
        ],
    )
    store.save_session_meta(
        session_id="test-session-001",
        meta=SessionMeta(
            resume_json='{"projects": []}',
            position="백엔드 개발자",
            interview_type="technical",
        ),
    )


class TestChatAgent:
    """채팅 에이전트 테스트"""

    async def test_agent_success(self):
        """정상 실행"""
        from app.domain.interview.chat_agent import run_chat_agent

        with patch(
            "app.domain.interview.chat_agent.generate_chat_response",
            new_callable=AsyncMock,
            return_value=SAMPLE_CHAT_OUTPUT,
        ):
            result, error, turn_count = await run_chat_agent(
                resume_json='{"projects": []}',
                position="백엔드 개발자",
                interview_type="technical",
                question_text="질문",
                question_intent="의도",
                related_project=None,
                answer="답변",
            )

        assert result == SAMPLE_CHAT_OUTPUT
        assert error is None

    async def test_agent_timeout(self):
        """타임아웃 시 에러 반환"""
        from app.domain.interview.chat_agent import run_chat_agent

        with patch(
            "app.domain.interview.chat_agent.generate_chat_response",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            result, error, turn_count = await run_chat_agent(
                resume_json='{"projects": []}',
                position="백엔드 개발자",
                interview_type="technical",
                question_text="질문",
                question_intent="의도",
                related_project=None,
                answer="답변",
            )

        assert result is None
        assert "타임아웃" in error

    async def test_agent_exception(self):
        """예외 발생 시 에러 반환"""
        from app.domain.interview.chat_agent import run_chat_agent

        with patch(
            "app.domain.interview.chat_agent.generate_chat_response",
            new_callable=AsyncMock,
            side_effect=ValueError("LLM 파싱 실패"),
        ):
            result, error, turn_count = await run_chat_agent(
                resume_json='{"projects": []}',
                position="백엔드 개발자",
                interview_type="technical",
                question_text="질문",
                question_intent="의도",
                related_project=None,
                answer="답변",
            )

        assert result is None
        assert "실패" in error

    async def test_agent_no_follow_up(self):
        """후속 질문 없는 경우"""
        from app.domain.interview.chat_agent import run_chat_agent

        output = ChatOutput(message="좋은 답변입니다", follow_up_question=None)

        with patch(
            "app.domain.interview.chat_agent.generate_chat_response",
            new_callable=AsyncMock,
            return_value=output,
        ):
            result, error, turn_count = await run_chat_agent(
                resume_json='{"projects": []}',
                position="백엔드 개발자",
                interview_type="technical",
                question_text="질문",
                question_intent="의도",
                related_project=None,
                answer="답변",
            )

        assert result.follow_up_question is None
        assert error is None


class TestChatEndpoint:
    """채팅 API 엔드포인트 테스트"""

    async def test_chat_success(self, async_client):
        """정상 채팅 응답"""
        mock_store = InterviewContextStore()
        _setup_store(mock_store)

        with (
            patch(
                "app.api.v2.chat.interview_context_store",
                mock_store,
            ),
            patch(
                "app.api.v2.chat.run_chat_agent",
                new_callable=AsyncMock,
                return_value=(SAMPLE_CHAT_OUTPUT, None, 1),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=SAMPLE_CHAT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "좋은 답변입니다"
        assert data["followUpQuestion"] is not None

    async def test_chat_session_expired(self, async_client):
        """세션 만료 시 실패 응답"""
        mock_store = InterviewContextStore()

        with patch(
            "app.api.v2.chat.interview_context_store",
            mock_store,
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=SAMPLE_CHAT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "만료" in data["error"]["message"]

    async def test_chat_question_not_found(self, async_client):
        """질문 ID 미발견 시 실패 응답"""
        mock_store = InterviewContextStore()
        mock_store.save(
            session_id="test-session-001",
            contexts=[
                QuestionContext(
                    question_id="q-other",
                    question_text="다른 질문",
                    intent="다른 의도",
                    related_project=None,
                ),
            ],
        )

        with patch(
            "app.api.v2.chat.interview_context_store",
            mock_store,
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=SAMPLE_CHAT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "찾을 수 없습니다" in data["error"]["message"]

    async def test_chat_session_meta_expired(self, async_client):
        """세션 메타데이터 만료 시 실패 응답"""
        mock_store = InterviewContextStore()
        mock_store.save(
            session_id="test-session-001",
            contexts=[
                QuestionContext(
                    question_id="q-test-001",
                    question_text="질문",
                    intent="의도",
                    related_project=None,
                ),
            ],
        )

        with patch(
            "app.api.v2.chat.interview_context_store",
            mock_store,
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=SAMPLE_CHAT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "메타데이터" in data["error"]["message"]

    async def test_chat_agent_failure(self, async_client):
        """에이전트 실패 시 failed 응답"""
        mock_store = InterviewContextStore()
        _setup_store(mock_store)

        with (
            patch(
                "app.api.v2.chat.interview_context_store",
                mock_store,
            ),
            patch(
                "app.api.v2.chat.run_chat_agent",
                new_callable=AsyncMock,
                return_value=(None, "LLM 호출 실패", 0),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=SAMPLE_CHAT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "LLM" in data["error"]["message"]

    async def test_chat_validation_empty_answer(self, async_client):
        """빈 answer 시 422"""
        request = {**SAMPLE_CHAT_REQUEST, "answer": ""}
        response = await async_client.post(
            "/api/v2/interview/chat",
            json=request,
        )
        assert response.status_code == 422


class TestMultiturnWorkflow:
    """멀티턴 채팅 워크플로우 통합 테스트"""

    def _make_chat_output(self, message: str, follow_up: str | None = None) -> ChatOutput:
        return ChatOutput(message=message, follow_up_question=follow_up)

    async def test_first_turn_generates_response(self):
        """첫 턴에서 초기 응답 생성 확인"""
        from langgraph.checkpoint.memory import MemorySaver

        from app.domain.interview.chat_workflow import create_chat_workflow

        checkpointer = MemorySaver()
        workflow = create_chat_workflow(checkpointer=checkpointer)

        first_output = self._make_chat_output("잘 답변하셨습니다", "구체적인 사례를 들어주세요")

        with patch(
            "app.domain.interview.chat_workflow.generate_chat_response",
            new_callable=AsyncMock,
            return_value=first_output,
        ):
            initial_state = {
                "resume_json": '{"projects": []}',
                "position": "백엔드 개발자",
                "interview_type": "technical",
                "question_text": "비동기 처리의 장점은?",
                "question_intent": "비동기 이해도",
                "related_project": None,
                "session_id": "test-session",
                "messages": [{"role": "human", "content": "async/await를 사용합니다"}],
                "turn_count": 0,
                "error_message": None,
                "last_response": None,
                "last_follow_up": None,
            }
            config = {"configurable": {"thread_id": "test-thread-first-turn"}}
            result = await workflow.ainvoke(initial_state, config=config)

        assert result["last_response"] == "잘 답변하셨습니다"
        assert result["last_follow_up"] == "구체적인 사례를 들어주세요"
        assert result["turn_count"] == 1

    async def test_multiturn_accumulates_messages(self):
        """멀티턴에서 대화 이력 누적 확인"""
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.types import Command

        from app.domain.interview.chat_workflow import create_chat_workflow

        checkpointer = MemorySaver()
        workflow = create_chat_workflow(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test-thread-multiturn"}}

        first_output = self._make_chat_output("좋은 답변입니다", "더 자세히 설명해주세요")
        second_output = self._make_chat_output("이해했습니다", None)

        with patch(
            "app.domain.interview.chat_workflow.generate_chat_response",
            new_callable=AsyncMock,
            return_value=first_output,
        ):
            initial_state = {
                "resume_json": '{"projects": []}',
                "position": "백엔드 개발자",
                "interview_type": "technical",
                "question_text": "REST API 설계 원칙은?",
                "question_intent": "API 설계 이해",
                "related_project": None,
                "session_id": "test-session",
                "messages": [{"role": "human", "content": "자원 중심 설계를 합니다"}],
                "turn_count": 0,
                "error_message": None,
                "last_response": None,
                "last_follow_up": None,
            }
            first_result = await workflow.ainvoke(initial_state, config=config)

        assert first_result["turn_count"] == 1

        with patch(
            "app.domain.interview.chat_workflow.generate_chat_response_with_history",
            new_callable=AsyncMock,
            return_value=second_output,
        ):
            second_result = await workflow.ainvoke(
                Command(resume="HTTP 메서드를 적절히 활용합니다"),
                config=config,
            )

        assert second_result["turn_count"] == 2
        messages = second_result["messages"]
        roles = [m["role"] for m in messages]
        assert roles.count("human") == 2
        assert roles.count("ai") == 2

    async def test_workflow_ends_on_error(self):
        """respond_node 에러 시 워크플로우 종료 확인"""
        from langgraph.checkpoint.memory import MemorySaver

        from app.domain.interview.chat_workflow import create_chat_workflow

        checkpointer = MemorySaver()
        workflow = create_chat_workflow(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test-thread-error"}}

        with patch(
            "app.domain.interview.chat_workflow.generate_chat_response",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM 호출 실패"),
        ):
            initial_state = {
                "resume_json": '{"projects": []}',
                "position": "백엔드 개발자",
                "interview_type": "technical",
                "question_text": "오류 시나리오 질문",
                "question_intent": "테스트",
                "related_project": None,
                "session_id": "test-session",
                "messages": [{"role": "human", "content": "답변입니다"}],
                "turn_count": 0,
                "error_message": None,
                "last_response": None,
                "last_follow_up": None,
            }
            result = await workflow.ainvoke(initial_state, config=config)

        assert result["error_message"] is not None
        assert "실패" in result["error_message"]

    async def test_workflow_ends_on_max_turns(self):
        """최대 턴 도달 시 워크플로우 종료 확인"""
        from langgraph.checkpoint.memory import MemorySaver

        from app.domain.interview.chat_schemas import MAX_CHAT_TURNS
        from app.domain.interview.chat_workflow import create_chat_workflow

        checkpointer = MemorySaver()
        workflow = create_chat_workflow(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "test-thread-max-turns"}}

        response = self._make_chat_output("마지막 응답", None)

        with (
            patch(
                "app.domain.interview.chat_workflow.generate_chat_response",
                new_callable=AsyncMock,
                return_value=response,
            ),
            patch(
                "app.domain.interview.chat_workflow.generate_chat_response_with_history",
                new_callable=AsyncMock,
                return_value=response,
            ),
        ):
            initial_state = {
                "resume_json": '{"projects": []}',
                "position": "백엔드 개발자",
                "interview_type": "technical",
                "question_text": "최대 턴 테스트",
                "question_intent": "테스트",
                "related_project": None,
                "session_id": "test-session",
                "messages": [{"role": "human", "content": "첫 답변"}],
                "turn_count": MAX_CHAT_TURNS - 1,
                "error_message": None,
                "last_response": None,
                "last_follow_up": None,
            }
            result = await workflow.ainvoke(initial_state, config=config)

        assert result["turn_count"] >= MAX_CHAT_TURNS
        assert result["error_message"] is None

    async def test_workflow_without_checkpointer_falls_back(self):
        """체크포인터 없이 create_chat_workflow 호출 시 단순 컴파일 확인"""
        from app.domain.interview.chat_workflow import create_chat_workflow

        workflow = create_chat_workflow(checkpointer=None)
        assert workflow is not None


class TestInterviewContextStore:
    """InterviewContextStore 유닛 테스트"""

    def test_save_and_get(self):
        """저장 후 조회"""
        store = InterviewContextStore()
        ctx = QuestionContext(
            question_id="q1",
            question_text="질문",
            intent="의도",
            related_project=None,
        )
        store.save(session_id="session-1", contexts=[ctx])
        result = store.get("session-1")
        assert result is not None
        assert "q1" in result

    def test_get_nonexistent(self):
        """존재하지 않는 키 조회 시 None"""
        store = InterviewContextStore()
        assert store.get("nonexistent") is None

    def test_session_meta_save_and_get(self):
        """세션 메타 저장 후 조회"""
        store = InterviewContextStore()
        meta = SessionMeta(
            resume_json="{}",
            position="백엔드",
            interview_type="technical",
        )
        store.save_session_meta(session_id="session-1", meta=meta)
        result = store.get_session_meta("session-1")
        assert result is not None
        assert result.position == "백엔드"

    def test_ttl_expiry(self):
        """TTL 만료 시 데이터 삭제"""
        store = InterviewContextStore(ttl_seconds=0)
        ctx = QuestionContext(
            question_id="q1",
            question_text="질문",
            intent="의도",
            related_project=None,
        )
        store.save(session_id="session-1", contexts=[ctx])
        store.save_session_meta(
            session_id="session-1",
            meta=SessionMeta(
                resume_json="{}",
                position="백엔드",
                interview_type="technical",
            ),
        )

        import time

        time.sleep(0.01)
        assert store.get("session-1") is None
        assert store.get_session_meta("session-1") is None
