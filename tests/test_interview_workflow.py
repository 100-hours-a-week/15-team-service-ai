from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import ErrorCode
from app.domain.interview.schemas import (
    InterviewEvaluationOutput,
    InterviewQuestion,
    InterviewQuestionsOutput,
    InterviewState,
)
from app.domain.interview.workflow import evaluate_node, generate_node


class TestInterviewGenerateNode:
    """면접 질문 generate_node 테스트"""

    @pytest.fixture
    def base_state(self) -> InterviewState:
        """기본 상태"""
        return InterviewState(
            resume_json='{"projects": []}',
            interview_type="technical",
            position="백엔드 개발자",
            question_count=5,
        )

    @pytest.mark.asyncio
    async def test_generate_success(self, base_state):
        """정상 면접 질문 생성"""
        mock_questions = InterviewQuestionsOutput(
            questions=[
                InterviewQuestion(
                    question="FastAPI의 비동기 처리 방식을 설명해주세요",
                    intent="비동기 프로그래밍 이해도 확인",
                    related_project="test-project",
                )
            ]
        )

        with patch(
            "app.domain.interview.workflow.generate_interview",
            new_callable=AsyncMock,
            return_value=mock_questions,
        ):
            result = await generate_node(base_state)

        assert result["questions"] == mock_questions
        assert result.get("error_code") is None

    @pytest.mark.asyncio
    async def test_generate_retry_increments_count(self, base_state):
        """재시도 시 retry_count 증가"""
        state_with_fail = dict(base_state)
        state_with_fail["evaluation"] = "fail"
        state_with_fail["retry_count"] = 1

        mock_questions = InterviewQuestionsOutput(
            questions=[
                InterviewQuestion(
                    question="테스트 질문",
                    intent="테스트 의도",
                )
            ]
        )

        with patch(
            "app.domain.interview.workflow.generate_interview",
            new_callable=AsyncMock,
            return_value=mock_questions,
        ):
            result = await generate_node(state_with_fail)

        assert result["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_generate_connect_error(self, base_state):
        """LLM 서버 연결 실패 시 에러 상태"""
        with patch(
            "app.domain.interview.workflow.generate_interview",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await generate_node(base_state)

        assert result["error_code"] == ErrorCode.LLM_API_ERROR
        assert "연결 실패" in result["error_message"]

    @pytest.mark.asyncio
    async def test_generate_timeout_error(self, base_state):
        """LLM 요청 타임아웃 시 에러 상태"""
        with patch(
            "app.domain.interview.workflow.generate_interview",
            new_callable=AsyncMock,
            side_effect=httpx.ReadTimeout("Request timed out"),
        ):
            result = await generate_node(base_state)

        assert result["error_code"] == ErrorCode.LLM_API_ERROR
        assert "타임아웃" in result["error_message"]

    @pytest.mark.asyncio
    async def test_generate_http_error(self, base_state):
        """LLM HTTP 오류 시 에러 상태"""
        mock_response = httpx.Response(500, request=httpx.Request("POST", "test"))
        http_error = httpx.HTTPStatusError(
            "Server Error", request=mock_response.request, response=mock_response
        )

        with patch(
            "app.domain.interview.workflow.generate_interview",
            new_callable=AsyncMock,
            side_effect=http_error,
        ):
            result = await generate_node(base_state)

        assert result["error_code"] == ErrorCode.LLM_API_ERROR
        assert "HTTP 500" in result["error_message"]

    @pytest.mark.asyncio
    async def test_generate_value_error(self, base_state):
        """데이터 오류 시 에러 상태"""
        with patch(
            "app.domain.interview.workflow.generate_interview",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid format"),
        ):
            result = await generate_node(base_state)

        assert result["error_code"] == ErrorCode.INTERVIEW_GENERATE_ERROR
        assert "면접 질문 생성 실패" in result["error_message"]


class TestInterviewEvaluateNode:
    """면접 질문 evaluate_node 테스트"""

    @pytest.fixture
    def base_state(self) -> InterviewState:
        """평가 가능한 기본 상태"""
        return InterviewState(
            resume_json='{"projects": []}',
            interview_type="technical",
            position="백엔드 개발자",
            question_count=5,
            questions=InterviewQuestionsOutput(
                questions=[
                    InterviewQuestion(
                        question="FastAPI의 비동기 처리 방식을 설명해주세요",
                        intent="비동기 프로그래밍 이해도 확인",
                        related_project="test-project",
                    )
                ]
            ),
            retry_count=0,
        )

    @pytest.mark.asyncio
    async def test_evaluate_pass(self, base_state):
        """평가 통과"""
        eval_result = InterviewEvaluationOutput(
            result="pass",
            violated_rule=None,
            violated_item=None,
            feedback="모든 규칙 준수",
        )

        with patch(
            "app.domain.interview.workflow.evaluate_interview",
            new_callable=AsyncMock,
            return_value=eval_result,
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "pass"

    @pytest.mark.asyncio
    async def test_evaluate_fail(self, base_state):
        """평가 실패 - 재시도 유도"""
        eval_result = InterviewEvaluationOutput(
            result="fail",
            violated_rule=6,
            violated_item="프로젝트 그룹핑",
            feedback="같은 프로젝트 질문이 인접하지 않음",
        )

        with patch(
            "app.domain.interview.workflow.evaluate_interview",
            new_callable=AsyncMock,
            return_value=eval_result,
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "fail"
        assert "인접하지 않음" in result["evaluation_feedback"]

    @pytest.mark.asyncio
    async def test_evaluate_fallback_on_connection_error(self, base_state):
        """Gemini 연결 실패 시 pass로 폴백"""
        with patch(
            "app.domain.interview.workflow.evaluate_interview",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Gemini 연결 실패"),
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "pass"

    @pytest.mark.asyncio
    async def test_evaluate_fallback_on_timeout(self, base_state):
        """Gemini 타임아웃 시 pass로 폴백"""
        with patch(
            "app.domain.interview.workflow.evaluate_interview",
            new_callable=AsyncMock,
            side_effect=httpx.ReadTimeout("Request timed out"),
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "pass"

    @pytest.mark.asyncio
    async def test_evaluate_fallback_on_parse_error(self, base_state):
        """파싱 오류 시 pass로 폴백"""
        with patch(
            "app.domain.interview.workflow.evaluate_interview",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid JSON"),
        ):
            result = await evaluate_node(base_state)

        assert result["evaluation"] == "pass"
