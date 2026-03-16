from unittest.mock import AsyncMock, patch

from app.domain.interview.feedback_schemas import FeedbackOutput, OverallFeedbackOutput
from app.domain.interview.schemas import InterviewQuestion, InterviewQuestionsOutput

SAMPLE_INTERVIEW_REQUEST = {
    "resumeId": 1,
    "content": {
        "projects": [
            {
                "name": "테스트 프로젝트",
                "repoUrl": "https://github.com/testuser/testrepo",
                "techStack": ["Python", "FastAPI"],
                "description": "FastAPI 기반 백엔드 서비스",
            }
        ]
    },
    "type": "technical",
    "position": "백엔드 개발자",
}

SAMPLE_INTERVIEW_QUESTIONS_OUTPUT = InterviewQuestionsOutput(
    questions=[
        InterviewQuestion(
            question="FastAPI에서 비동기 처리의 장점은 무엇인가요?",
            intent="비동기 프로그래밍 이해도",
            related_project="테스트 프로젝트",
            category="Python/FastAPI",
        ),
        InterviewQuestion(
            question="REST API 설계 시 중요한 원칙은?",
            intent="API 설계 이해도",
            related_project="테스트 프로젝트",
            category="API 설계/통합",
        ),
    ]
)

SAMPLE_CHAT_REQUEST = {
    "aiSessionId": "test-session-001",
    "questionId": "q-001",
    "answer": "FastAPI에서 async/await를 사용하여 비동기 처리를 구현했습니다",
}

SAMPLE_FEEDBACK_REQUEST = {
    "aiSessionId": "test-session-001",
    "interviewType": "TECHNICAL",
    "position": "백엔드 개발자",
    "company": "테스트 회사",
    "messages": [
        {
            "turnNo": 1,
            "question": "FastAPI 비동기 처리란?",
            "answer": "async/await 패턴을 사용합니다",
            "answerInputType": "TEXT",
            "askedAt": "2026-02-21T10:00:00Z",
            "answeredAt": "2026-02-21T10:00:30Z",
        }
    ],
}

SAMPLE_FEEDBACK_OUTPUT = FeedbackOutput(
    score=8,
    strengths=["비동기 개념 이해", "명확한 설명"],
    improvements=["구체적 사례 추가 필요"],
    model_answer="FastAPI의 비동기 처리는 I/O 바운드 작업에서 성능을 크게 향상시킵니다",
)

SAMPLE_OVERALL_OUTPUT = OverallFeedbackOutput(
    overall_score=8,
    summary="전반적으로 양호한 답변을 제공했습니다",
    key_strengths=["기술적 이해도 양호"],
    key_improvements=["실무 경험 관련 사례 보강 필요"],
)


class TestInterviewGenerateEndpoint:
    """POST /api/v2/interview 면접 질문 생성 엔드포인트 통합 테스트"""

    async def test_generate_success(self, async_client):
        """정상 요청 시 질문 목록과 aiSessionId 반환"""
        with patch(
            "app.api.v2.interview.run_interview_agent",
            new_callable=AsyncMock,
            return_value=(SAMPLE_INTERVIEW_QUESTIONS_OUTPUT, None),
        ):
            response = await async_client.post(
                "/api/v2/interview",
                json=SAMPLE_INTERVIEW_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "aiSessionId" in data
        assert data["aiSessionId"] is not None
        assert isinstance(data["questions"], list)
        assert len(data["questions"]) == 2
        assert data["questions"][0]["questionId"] == "q-001"
        assert "text" in data["questions"][0]

    async def test_generate_agent_failure_returns_failed(self, async_client):
        """에이전트 실패 시 failed 응답 반환"""
        with patch(
            "app.api.v2.interview.run_interview_agent",
            new_callable=AsyncMock,
            return_value=(None, "LLM 호출 실패"),
        ):
            response = await async_client.post(
                "/api/v2/interview",
                json=SAMPLE_INTERVIEW_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"]["message"] == "LLM 호출 실패"

    async def test_generate_missing_resume_id_returns_422(self, async_client):
        """resumeId 누락 시 422 반환"""
        request = {**SAMPLE_INTERVIEW_REQUEST}
        del request["resumeId"]
        response = await async_client.post("/api/v2/interview", json=request)
        assert response.status_code == 422

    async def test_generate_invalid_type_returns_422(self, async_client):
        """잘못된 interview type 시 422 반환"""
        request = {**SAMPLE_INTERVIEW_REQUEST, "type": "invalid_type"}
        response = await async_client.post("/api/v2/interview", json=request)
        assert response.status_code == 422

    async def test_generate_empty_projects_returns_422(self, async_client):
        """빈 projects 배열 시 422 반환"""
        request = {
            **SAMPLE_INTERVIEW_REQUEST,
            "content": {"projects": []},
        }
        response = await async_client.post("/api/v2/interview", json=request)
        assert response.status_code == 422

    async def test_generate_stores_session_context(self, async_client):
        """성공 시 세션 컨텍스트가 저장되는지 확인"""
        from app.domain.interview.store import interview_context_store

        with patch(
            "app.api.v2.interview.run_interview_agent",
            new_callable=AsyncMock,
            return_value=(SAMPLE_INTERVIEW_QUESTIONS_OUTPUT, None),
        ):
            response = await async_client.post(
                "/api/v2/interview",
                json=SAMPLE_INTERVIEW_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        session_id = data["aiSessionId"]

        contexts = interview_context_store.get(session_id)
        assert contexts is not None
        meta = interview_context_store.get_session_meta(session_id)
        assert meta is not None
        assert meta.position == "백엔드 개발자"
        assert meta.interview_type == "technical"


class TestChatEndpointIntegration:
    """POST /api/v2/interview/chat 면접 채팅 엔드포인트 통합 테스트"""

    async def test_chat_success_with_checkpointer(self, async_client):
        """체크포인터가 있는 상태에서 채팅 성공"""
        from app.domain.interview.chat_schemas import ChatOutput
        from app.domain.interview.store import (
            InterviewContextStore,
            QuestionContext,
            SessionMeta,
        )

        mock_store = InterviewContextStore()
        mock_store.save(
            session_id="test-session-001",
            contexts=[
                QuestionContext(
                    question_id="q-001",
                    question_text="비동기 처리의 장점은?",
                    intent="비동기 이해도",
                    related_project="테스트 프로젝트",
                )
            ],
        )
        mock_store.save_session_meta(
            session_id="test-session-001",
            meta=SessionMeta(
                resume_json='{"projects": []}',
                position="백엔드 개발자",
                interview_type="technical",
            ),
        )

        chat_output = ChatOutput(
            message="잘 설명하셨습니다",
            follow_up_question="구체적인 사례를 들어주시겠어요?",
        )

        with (
            patch("app.api.v2.chat.interview_context_store", mock_store),
            patch(
                "app.api.v2.chat.run_chat_agent",
                new_callable=AsyncMock,
                return_value=(chat_output, None, 1),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=SAMPLE_CHAT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "잘 설명하셨습니다"
        assert data["followUpQuestion"] == "구체적인 사례를 들어주시겠어요?"
        assert data["turnNumber"] == 1

    async def test_chat_follow_up_suppressed_at_max_turns(self, async_client):
        """최대 꼬리질문 횟수 도달 시 follow_up 제거"""
        from app.domain.interview.chat_schemas import ChatOutput
        from app.domain.interview.store import (
            InterviewContextStore,
            QuestionContext,
            SessionMeta,
        )

        mock_store = InterviewContextStore()
        mock_store.save(
            session_id="test-session-001",
            contexts=[
                QuestionContext(
                    question_id="q-001",
                    question_text="질문",
                    intent="의도",
                    related_project=None,
                )
            ],
        )
        mock_store.save_session_meta(
            session_id="test-session-001",
            meta=SessionMeta(
                resume_json="{}",
                position="백엔드 개발자",
                interview_type="technical",
            ),
        )

        chat_output = ChatOutput(
            message="응답 메시지",
            follow_up_question="이 질문은 제거되어야 합니다",
        )

        with (
            patch("app.api.v2.chat.interview_context_store", mock_store),
            patch(
                "app.api.v2.chat.run_chat_agent",
                new_callable=AsyncMock,
                return_value=(chat_output, None, 4),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=SAMPLE_CHAT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["followUpQuestion"] is None

    async def test_chat_follow_up_retry_on_first_skip_answer(self, async_client):
        """첫 번째 모르겠다 답변 시 LLM 힌트 유지"""
        from app.domain.interview.chat_schemas import ChatOutput
        from app.domain.interview.store import (
            InterviewContextStore,
            QuestionContext,
            SessionMeta,
        )

        mock_store = InterviewContextStore()
        mock_store.save(
            session_id="test-session-001",
            contexts=[
                QuestionContext(
                    question_id="q-001",
                    question_text="어려운 질문",
                    intent="의도",
                    related_project=None,
                )
            ],
        )
        mock_store.save_session_meta(
            session_id="test-session-001",
            meta=SessionMeta(
                resume_json="{}",
                position="백엔드 개발자",
                interview_type="technical",
            ),
        )

        chat_output = ChatOutput(
            message="괜찮습니다",
            follow_up_question="원래 꼬리질문",
        )

        skip_request = {**SAMPLE_CHAT_REQUEST, "answer": "모르겠습니다"}

        with (
            patch("app.api.v2.chat.interview_context_store", mock_store),
            patch(
                "app.api.v2.chat.run_chat_agent",
                new_callable=AsyncMock,
                return_value=(chat_output, None, 1),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=skip_request,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["followUpQuestion"] is not None
        assert data["followUpQuestion"] == "원래 꼬리질문"

    async def test_chat_follow_up_suppressed_on_second_skip_answer(self, async_client):
        """두 번째 연속 모르겠다 답변 시 follow_up 제거"""
        from app.domain.interview.chat_schemas import ChatOutput
        from app.domain.interview.store import (
            InterviewContextStore,
            QuestionContext,
            SessionMeta,
        )

        mock_store = InterviewContextStore()
        mock_store.save(
            session_id="test-session-001",
            contexts=[
                QuestionContext(
                    question_id="q-001",
                    question_text="어려운 질문",
                    intent="의도",
                    related_project=None,
                )
            ],
        )
        mock_store.save_session_meta(
            session_id="test-session-001",
            meta=SessionMeta(
                resume_json="{}",
                position="백엔드 개발자",
                interview_type="technical",
            ),
        )
        mock_store.increment_skip_count("test-session-001", "q-001")

        chat_output = ChatOutput(
            message="괜찮습니다",
            follow_up_question="이 질문도 제거되어야 합니다",
        )

        skip_request = {**SAMPLE_CHAT_REQUEST, "answer": "모르겠습니다"}

        with (
            patch("app.api.v2.chat.interview_context_store", mock_store),
            patch(
                "app.api.v2.chat.run_chat_agent",
                new_callable=AsyncMock,
                return_value=(chat_output, None, 1),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=skip_request,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["followUpQuestion"] is None


class TestFeedbackEndpointIntegration:
    """POST /api/v2/interview/end 면접 피드백 엔드포인트 통합 테스트"""

    async def test_feedback_success(self, async_client):
        """정상 요청 시 개별 + 종합 피드백 반환"""
        with (
            patch(
                "app.api.v2.feedback.run_feedback_agent",
                new_callable=AsyncMock,
                return_value=(SAMPLE_FEEDBACK_OUTPUT, None),
            ),
            patch(
                "app.api.v2.feedback.run_overall_feedback_agent",
                new_callable=AsyncMock,
                return_value=(SAMPLE_OVERALL_OUTPUT, None),
            ),
            patch("app.api.v2.feedback.interview_context_store"),
        ):
            response = await async_client.post(
                "/api/v2/interview/end",
                json=SAMPLE_FEEDBACK_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["feedbacks"] is not None
        assert len(data["feedbacks"]) == 1
        assert data["feedbacks"][0]["turnNo"] == 1
        assert data["feedbacks"][0]["score"] == 8
        assert data["overallFeedback"] is not None
        assert data["overallFeedback"]["overallScore"] == 8

    async def test_feedback_individual_failure_overall_success(self, async_client):
        """개별 피드백 실패해도 종합 피드백 성공 시 success 반환"""
        with (
            patch(
                "app.api.v2.feedback.run_feedback_agent",
                new_callable=AsyncMock,
                return_value=(None, "개별 피드백 생성 실패"),
            ),
            patch(
                "app.api.v2.feedback.run_overall_feedback_agent",
                new_callable=AsyncMock,
                return_value=(SAMPLE_OVERALL_OUTPUT, None),
            ),
            patch("app.api.v2.feedback.interview_context_store"),
        ):
            response = await async_client.post(
                "/api/v2/interview/end",
                json=SAMPLE_FEEDBACK_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["feedbacks"] is None or data["feedbacks"] == []
        assert data["overallFeedback"] is not None

    async def test_feedback_all_fail_returns_failed(self, async_client):
        """개별 + 종합 피드백 모두 실패 시 failed 반환"""
        with (
            patch(
                "app.api.v2.feedback.run_feedback_agent",
                new_callable=AsyncMock,
                return_value=(None, "개별 피드백 실패"),
            ),
            patch(
                "app.api.v2.feedback.run_overall_feedback_agent",
                new_callable=AsyncMock,
                return_value=(None, "종합 피드백 실패"),
            ),
            patch("app.api.v2.feedback.interview_context_store"),
        ):
            response = await async_client.post(
                "/api/v2/interview/end",
                json=SAMPLE_FEEDBACK_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] is not None

    async def test_feedback_missing_messages_returns_422(self, async_client):
        """messages 누락 시 422 반환"""
        request = {**SAMPLE_FEEDBACK_REQUEST}
        del request["messages"]
        response = await async_client.post("/api/v2/interview/end", json=request)
        assert response.status_code == 422

    async def test_feedback_invalid_interview_type_returns_422(self, async_client):
        """잘못된 interviewType 시 422 반환"""
        request = {**SAMPLE_FEEDBACK_REQUEST, "interviewType": "invalid_type"}
        response = await async_client.post("/api/v2/interview/end", json=request)
        assert response.status_code == 422

    async def test_feedback_too_many_messages_returns_422(self, async_client):
        """messages 20개 초과 시 422 반환"""
        messages = [
            {
                "turnNo": i + 1,
                "question": f"질문 {i + 1}",
                "answer": "답변",
                "answerInputType": "TEXT",
                "askedAt": "2026-02-21T10:00:00Z",
                "answeredAt": "2026-02-21T10:00:30Z",
            }
            for i in range(21)
        ]
        request = {**SAMPLE_FEEDBACK_REQUEST, "messages": messages}
        response = await async_client.post("/api/v2/interview/end", json=request)
        assert response.status_code == 422

    async def test_feedback_behavioral_interview_type(self, async_client):
        """BEHAVIORAL 타입 요청 정상 처리"""
        request = {**SAMPLE_FEEDBACK_REQUEST, "interviewType": "BEHAVIORAL"}

        with (
            patch(
                "app.api.v2.feedback.run_feedback_agent",
                new_callable=AsyncMock,
                return_value=(SAMPLE_FEEDBACK_OUTPUT, None),
            ),
            patch(
                "app.api.v2.feedback.run_overall_feedback_agent",
                new_callable=AsyncMock,
                return_value=(SAMPLE_OVERALL_OUTPUT, None),
            ),
            patch("app.api.v2.feedback.interview_context_store"),
        ):
            response = await async_client.post(
                "/api/v2/interview/end",
                json=request,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "success"


class TestChatSafetyNets:
    """채팅 API 안전장치 테스트 - 자기소개/장단점 null, 솔로 프로젝트 null"""

    async def test_self_presentation_forces_null_follow_up(self, async_client):
        """자기소개/장단점 질문에서 LLM이 꼬리질문을 생성해도 강제 null"""
        from app.domain.interview.chat_schemas import ChatOutput
        from app.domain.interview.store import (
            InterviewContextStore,
            QuestionContext,
            SessionMeta,
        )

        mock_store = InterviewContextStore()
        mock_store.save(
            session_id="test-session-001",
            contexts=[
                QuestionContext(
                    question_id="q-001",
                    question_text="본인의 장단점을 말씀해주세요",
                    intent="자기 분석 능력",
                    related_project=None,
                )
            ],
        )
        mock_store.save_session_meta(
            session_id="test-session-001",
            meta=SessionMeta(
                resume_json="{}",
                position="백엔드 개발자",
                interview_type="behavioral",
            ),
        )

        chat_output = ChatOutput(
            message="말씀 잘 들었습니다",
            follow_up_question="로그 분석 사례를 더 말씀해주시겠어요?",
        )

        with (
            patch("app.api.v2.chat.interview_context_store", mock_store),
            patch(
                "app.api.v2.chat.run_chat_agent",
                new_callable=AsyncMock,
                return_value=(chat_output, None, 1),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=SAMPLE_CHAT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["followUpQuestion"] is None

    async def test_solo_project_forces_null_follow_up(self, async_client):
        """솔로 프로젝트 답변 시 LLM이 팀 질문을 생성해도 강제 null"""
        from app.domain.interview.chat_schemas import ChatOutput
        from app.domain.interview.store import (
            InterviewContextStore,
            QuestionContext,
            SessionMeta,
        )

        mock_store = InterviewContextStore()
        mock_store.save(
            session_id="test-session-001",
            contexts=[
                QuestionContext(
                    question_id="q-001",
                    question_text="팀원과의 갈등 해결 경험을 말씀해주세요",
                    intent="갈등 해결 능력",
                    related_project="테스트 프로젝트",
                )
            ],
        )
        mock_store.save_session_meta(
            session_id="test-session-001",
            meta=SessionMeta(
                resume_json="{}",
                position="백엔드 개발자",
                interview_type="behavioral",
            ),
        )

        chat_output = ChatOutput(
            message="네, 알겠습니다",
            follow_up_question="팀원들과 어떻게 소통하셨나요?",
        )

        solo_request = {
            **SAMPLE_CHAT_REQUEST,
            "answer": "혼자 진행한 프로젝트여서 팀원은 없었습니다",
        }

        with (
            patch("app.api.v2.chat.interview_context_store", mock_store),
            patch(
                "app.api.v2.chat.run_chat_agent",
                new_callable=AsyncMock,
                return_value=(chat_output, None, 1),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/chat",
                json=solo_request,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["followUpQuestion"] is None
