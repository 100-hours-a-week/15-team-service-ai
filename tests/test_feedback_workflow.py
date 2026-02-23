import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import ErrorCode
from app.domain.interview.feedback_schemas import (
    FeedbackEvaluationOutput,
    FeedbackOutput,
    OverallFeedbackEvaluationOutput,
    OverallFeedbackOutput,
)

SAMPLE_FEEDBACK_STATE = {
    "resume_json": "없음",
    "position": "백엔드 개발자",
    "interview_type": "technical",
    "question_text": "FastAPI에서 비동기 처리의 장점은?",
    "question_intent": "비동기 프로그래밍 이해도",
    "related_project": "test-project",
    "answer": "FastAPI는 async/await를 지원합니다",
    "session_id": "test-session",
    "retry_count": 0,
}

SAMPLE_FEEDBACK_OUTPUT = FeedbackOutput(
    score=7,
    strengths=["비동기 개념 이해"],
    improvements=["구체적 사례 부족"],
    model_answer="FastAPI의 비동기 처리는 I/O 바운드 작업에서 성능 향상",
)

SAMPLE_OVERALL_STATE = {
    "resume_json": "없음",
    "position": "백엔드 개발자",
    "interview_type": "technical",
    "qa_pairs_json": '[{"question": "Q1", "answer": "A1"}]',
    "session_id": "test-session",
    "retry_count": 0,
}

SAMPLE_OVERALL_OUTPUT = OverallFeedbackOutput(
    overall_score=7,
    summary="전반적으로 양호한 답변",
    key_strengths=["기술 이해도 양호"],
    key_improvements=["실무 경험 부족"],
)


class TestGenerateFeedbackNode:
    """개별 피드백 생성 노드 테스트"""

    async def test_generate_success(self):
        """정상 생성"""
        from app.domain.interview.feedback_workflow import (
            generate_feedback_node,
        )

        with patch(
            "app.domain.interview.feedback_workflow.generate_feedback",
            new_callable=AsyncMock,
            return_value=SAMPLE_FEEDBACK_OUTPUT,
        ):
            result = await generate_feedback_node(SAMPLE_FEEDBACK_STATE)

        assert result["feedback_result"] == SAMPLE_FEEDBACK_OUTPUT
        assert result["retry_count"] == 0

    async def test_generate_retry_increments_count(self):
        """평가 실패 후 재시도 시 retry_count 증가"""
        from app.domain.interview.feedback_workflow import (
            generate_feedback_node,
        )

        retry_state = {
            **SAMPLE_FEEDBACK_STATE,
            "evaluation": "fail",
            "retry_count": 0,
        }

        with patch(
            "app.domain.interview.feedback_workflow.generate_feedback",
            new_callable=AsyncMock,
            return_value=SAMPLE_FEEDBACK_OUTPUT,
        ):
            result = await generate_feedback_node(retry_state)

        assert result["retry_count"] == 1
        assert result["feedback_result"] == SAMPLE_FEEDBACK_OUTPUT

    async def test_generate_connection_error(self):
        """연결 오류 시 에러 상태 반환"""
        from app.domain.interview.feedback_workflow import (
            generate_feedback_node,
        )

        with patch(
            "app.domain.interview.feedback_workflow.generate_feedback",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("연결 실패"),
        ):
            result = await generate_feedback_node(SAMPLE_FEEDBACK_STATE)

        assert result.get("error_code") == ErrorCode.LLM_API_ERROR

    async def test_generate_value_error(self):
        """파싱 오류 시 에러 상태 반환"""
        from app.domain.interview.feedback_workflow import (
            generate_feedback_node,
        )

        with patch(
            "app.domain.interview.feedback_workflow.generate_feedback",
            new_callable=AsyncMock,
            side_effect=ValueError("파싱 실패"),
        ):
            result = await generate_feedback_node(SAMPLE_FEEDBACK_STATE)

        assert result.get("error_code") == ErrorCode.FEEDBACK_GENERATE_ERROR


class TestEvaluateFeedbackNode:
    """개별 피드백 평가 노드 테스트"""

    async def test_evaluate_pass(self):
        """평가 통과"""
        from app.domain.interview.feedback_workflow import (
            evaluate_feedback_node,
        )

        state = {
            **SAMPLE_FEEDBACK_STATE,
            "feedback_result": SAMPLE_FEEDBACK_OUTPUT,
        }

        eval_result = FeedbackEvaluationOutput(
            result="pass",
            feedback="피드백이 적절합니다",
        )

        with patch(
            "app.domain.interview.feedback_workflow.evaluate_feedback",
            new_callable=AsyncMock,
            return_value=eval_result,
        ):
            result = await evaluate_feedback_node(state)

        assert result["evaluation"] == "pass"

    async def test_evaluate_fail(self):
        """평가 실패"""
        from app.domain.interview.feedback_workflow import (
            evaluate_feedback_node,
        )

        state = {
            **SAMPLE_FEEDBACK_STATE,
            "feedback_result": SAMPLE_FEEDBACK_OUTPUT,
        }

        eval_result = FeedbackEvaluationOutput(
            result="fail",
            feedback="점수와 피드백이 불일치",
        )

        with patch(
            "app.domain.interview.feedback_workflow.evaluate_feedback",
            new_callable=AsyncMock,
            return_value=eval_result,
        ):
            result = await evaluate_feedback_node(state)

        assert result["evaluation"] == "fail"
        assert result["evaluation_feedback"] == "점수와 피드백이 불일치"

    async def test_evaluate_fallback_on_error(self):
        """평가 실패 시 pass로 폴백"""
        from app.domain.interview.feedback_workflow import (
            evaluate_feedback_node,
        )

        state = {
            **SAMPLE_FEEDBACK_STATE,
            "feedback_result": SAMPLE_FEEDBACK_OUTPUT,
        }

        with patch(
            "app.domain.interview.feedback_workflow.evaluate_feedback",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Gemini 연결 실패"),
        ):
            result = await evaluate_feedback_node(state)

        assert result["evaluation"] == "pass"


class TestGenerateOverallNode:
    """종합 피드백 생성 노드 테스트"""

    async def test_generate_overall_success(self):
        """종합 피드백 정상 생성"""
        from app.domain.interview.feedback_workflow import (
            generate_overall_node,
        )

        with patch(
            "app.domain.interview.feedback_workflow.generate_overall_feedback",
            new_callable=AsyncMock,
            return_value=SAMPLE_OVERALL_OUTPUT,
        ):
            result = await generate_overall_node(SAMPLE_OVERALL_STATE)

        assert result["feedback_result"] == SAMPLE_OVERALL_OUTPUT

    async def test_generate_overall_connection_error(self):
        """종합 피드백 연결 오류"""
        from app.domain.interview.feedback_workflow import (
            generate_overall_node,
        )

        with patch(
            "app.domain.interview.feedback_workflow.generate_overall_feedback",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("연결 실패"),
        ):
            result = await generate_overall_node(SAMPLE_OVERALL_STATE)

        assert result.get("error_code") == ErrorCode.LLM_API_ERROR


class TestEvaluateOverallNode:
    """종합 피드백 평가 노드 테스트"""

    async def test_evaluate_overall_pass(self):
        """종합 피드백 평가 통과"""
        from app.domain.interview.feedback_workflow import (
            evaluate_overall_node,
        )

        state = {
            **SAMPLE_OVERALL_STATE,
            "feedback_result": SAMPLE_OVERALL_OUTPUT,
        }

        eval_result = OverallFeedbackEvaluationOutput(
            result="pass",
            feedback="종합 피드백이 적절합니다",
        )

        with patch(
            "app.domain.interview.feedback_workflow.evaluate_overall_feedback",
            new_callable=AsyncMock,
            return_value=eval_result,
        ):
            result = await evaluate_overall_node(state)

        assert result["evaluation"] == "pass"


class TestFeedbackAgent:
    """개별 피드백 에이전트 테스트"""

    async def test_agent_success(self):
        """에이전트 정상 실행"""
        from app.domain.interview.feedback_agent import run_feedback_agent

        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(
            return_value={
                "feedback_result": SAMPLE_FEEDBACK_OUTPUT,
                "evaluation": "pass",
                "retry_count": 0,
            }
        )

        with (
            patch(
                "app.domain.interview.feedback_agent._feedback_workflow",
                mock_workflow,
            ),
            patch(
                "app.domain.interview.feedback_agent.get_langfuse_handler",
                return_value=None,
            ),
        ):
            result, error = await run_feedback_agent(
                resume_json="없음",
                position="백엔드 개발자",
                interview_type="technical",
                question_text="질문",
                question_intent="의도",
                related_project=None,
                answer="답변",
            )

        assert result == SAMPLE_FEEDBACK_OUTPUT
        assert error is None

    async def test_agent_workflow_error(self):
        """워크플로우 에러 상태 반환"""
        from app.domain.interview.feedback_agent import run_feedback_agent

        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(
            return_value={
                "error_code": ErrorCode.FEEDBACK_GENERATE_ERROR,
                "error_message": "피드백 생성 실패",
            }
        )

        with (
            patch(
                "app.domain.interview.feedback_agent._feedback_workflow",
                mock_workflow,
            ),
            patch(
                "app.domain.interview.feedback_agent.get_langfuse_handler",
                return_value=None,
            ),
        ):
            result, error = await run_feedback_agent(
                resume_json="없음",
                position="백엔드 개발자",
                interview_type="technical",
                question_text="질문",
                question_intent="의도",
                related_project=None,
                answer="답변",
            )

        assert result is None
        assert error == "피드백 생성 실패"

    async def test_agent_timeout(self):
        """에이전트 타임아웃"""
        from app.domain.interview.feedback_agent import run_feedback_agent

        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

        with (
            patch(
                "app.domain.interview.feedback_agent._feedback_workflow",
                mock_workflow,
            ),
            patch(
                "app.domain.interview.feedback_agent.get_langfuse_handler",
                return_value=None,
            ),
        ):
            result, error = await run_feedback_agent(
                resume_json="없음",
                position="백엔드 개발자",
                interview_type="technical",
                question_text="질문",
                question_intent="의도",
                related_project=None,
                answer="답변",
            )

        assert result is None
        assert "타임아웃" in error


class TestOverallFeedbackAgent:
    """종합 피드백 에이전트 테스트"""

    async def test_overall_agent_success(self):
        """종합 피드백 에이전트 정상 실행"""
        from app.domain.interview.feedback_agent import (
            run_overall_feedback_agent,
        )

        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(
            return_value={
                "feedback_result": SAMPLE_OVERALL_OUTPUT,
                "evaluation": "pass",
                "retry_count": 0,
            }
        )

        with (
            patch(
                "app.domain.interview.feedback_agent._overall_feedback_workflow",
                mock_workflow,
            ),
            patch(
                "app.domain.interview.feedback_agent.get_langfuse_handler",
                return_value=None,
            ),
        ):
            result, error = await run_overall_feedback_agent(
                resume_json="없음",
                position="백엔드 개발자",
                interview_type="technical",
                qa_pairs_json='[{"question": "Q", "answer": "A"}]',
            )

        assert result == SAMPLE_OVERALL_OUTPUT
        assert error is None

    async def test_overall_agent_error(self):
        """종합 피드백 에이전트 에러 반환"""
        from app.domain.interview.feedback_agent import (
            run_overall_feedback_agent,
        )

        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(
            return_value={
                "error_code": ErrorCode.FEEDBACK_GENERATE_ERROR,
                "error_message": "종합 피드백 생성 실패",
            }
        )

        with (
            patch(
                "app.domain.interview.feedback_agent._overall_feedback_workflow",
                mock_workflow,
            ),
            patch(
                "app.domain.interview.feedback_agent.get_langfuse_handler",
                return_value=None,
            ),
        ):
            result, error = await run_overall_feedback_agent(
                resume_json="없음",
                position="백엔드 개발자",
                interview_type="technical",
                qa_pairs_json='[{"question": "Q", "answer": "A"}]',
            )

        assert result is None
        assert error == "종합 피드백 생성 실패"


class TestFeedbackEndpoint:
    """피드백 API 엔드포인트 테스트"""

    SAMPLE_REQUEST = {
        "aiSessionId": "test-session",
        "interviewType": "TECHNICAL",
        "position": "백엔드 개발자",
        "company": "테스트회사",
        "messages": [
            {
                "turnNo": 1,
                "question": "FastAPI의 장점은?",
                "answer": "비동기 지원",
                "answerInputType": "text",
                "askedAt": "2026-02-20T10:00:00",
                "answeredAt": "2026-02-20T10:01:00",
            },
        ],
    }

    async def test_endpoint_all_success(self, async_client):
        """전체 성공 시 success 응답"""
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
        ):
            response = await async_client.post(
                "/api/v2/interview/end",
                json=self.SAMPLE_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["feedbacks"]) == 1
        assert data["feedbacks"][0]["score"] == 7
        assert data["overallFeedback"]["overallScore"] == 7

    async def test_endpoint_partial_success(self, async_client):
        """개별 피드백 실패 + 종합 성공 시 success 응답"""
        with (
            patch(
                "app.api.v2.feedback.run_feedback_agent",
                new_callable=AsyncMock,
                return_value=(None, "피드백 생성 실패"),
            ),
            patch(
                "app.api.v2.feedback.run_overall_feedback_agent",
                new_callable=AsyncMock,
                return_value=(SAMPLE_OVERALL_OUTPUT, None),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/end",
                json=self.SAMPLE_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["feedbacks"] is None
        assert data["overallFeedback"] is not None

    async def test_endpoint_all_failure(self, async_client):
        """전체 실패 시 failed 응답"""
        with (
            patch(
                "app.api.v2.feedback.run_feedback_agent",
                new_callable=AsyncMock,
                return_value=(None, "피드백 생성 실패"),
            ),
            patch(
                "app.api.v2.feedback.run_overall_feedback_agent",
                new_callable=AsyncMock,
                return_value=(None, "종합 피드백 실패"),
            ),
        ):
            response = await async_client.post(
                "/api/v2/interview/end",
                json=self.SAMPLE_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] is not None

    async def test_endpoint_messages_max_length(self, async_client):
        """messages 21개 초과 시 422"""
        messages = [
            {
                "turnNo": i,
                "question": f"질문 {i}",
                "answer": f"답변 {i}",
                "answerInputType": "text",
                "askedAt": "2026-02-20T10:00:00",
                "answeredAt": "2026-02-20T10:01:00",
            }
            for i in range(1, 22)
        ]
        request = {**self.SAMPLE_REQUEST, "messages": messages}

        response = await async_client.post(
            "/api/v2/interview/end",
            json=request,
        )

        assert response.status_code == 422


class TestFeedbackOutputValidation:
    """FeedbackOutput 필드 제약 테스트"""

    def test_score_within_range(self):
        """1-10 범위 내 점수는 유효"""
        output = FeedbackOutput(
            score=5,
            strengths=["좋음"],
            improvements=["개선 필요"],
            model_answer="모범 답안",
        )
        assert output.score == 5

    def test_score_below_range(self):
        """0 이하 점수는 ValidationError"""
        with pytest.raises(ValueError):
            FeedbackOutput(
                score=0,
                strengths=["좋음"],
                improvements=["개선 필요"],
                model_answer="모범 답안",
            )

    def test_score_above_range(self):
        """11 이상 점수는 ValidationError"""
        with pytest.raises(ValueError):
            FeedbackOutput(
                score=11,
                strengths=["좋음"],
                improvements=["개선 필요"],
                model_answer="모범 답안",
            )

    def test_overall_score_within_range(self):
        """종합 점수 1-10 범위 내 유효"""
        output = OverallFeedbackOutput(
            overall_score=8,
            summary="양호",
            key_strengths=["기술 이해"],
            key_improvements=["실무 경험"],
        )
        assert output.overall_score == 8

    def test_overall_score_below_range(self):
        """종합 점수 0 이하는 ValidationError"""
        with pytest.raises(ValueError):
            OverallFeedbackOutput(
                overall_score=0,
                summary="양호",
                key_strengths=["기술 이해"],
                key_improvements=["실무 경험"],
            )
