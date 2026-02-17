import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v2.schemas.resume_edit import (
    EditProjectOutput,
    EditResumeOutput,
)
from app.core.exceptions import ErrorCode
from app.domain.resume.schemas.base import EvaluationOutput

SAMPLE_EDIT_REQUEST = {
    "resumeId": 1,
    "content": {
        "projects": [
            {
                "name": "Health_advice_app",
                "repoUrl": "https://github.com/HongDay/Health_advice_app",
                "techStack": ["TensorFlow Lite", "NumPy", "Pandas", "Scikit-learn", "Flask"],
                "description": (
                    "- LSTM 기반 사용자 활동 분석 모델 구현\n"
                    "- Flask REST API 설계\n"
                    "- 데이터 전처리 파이프라인 구축\n"
                    "- 모델 경량화 및 최적화\n"
                    "- NumPy 기반 수치 연산 처리"
                ),
            }
        ]
    },
    "requestMessage": "온디바이스에 대한 내용을 추가해줘",
}

SAMPLE_EDITED_OUTPUT = EditResumeOutput(
    projects=[
        EditProjectOutput(
            name="Health_advice_app",
            repo_url="https://github.com/HongDay/Health_advice_app",
            tech_stack=["TensorFlow Lite", "NumPy", "Pandas", "Scikit-learn", "Flask"],
            description=(
                "- TensorFlow Lite 기반 온디바이스 AI 모델 구현\n"
                "- LSTM 활용 사용자 활동 패턴 분석\n"
                "- Flask REST API 설계\n"
                "- 데이터 전처리 파이프라인 구축\n"
                "- 모델 경량화 및 온디바이스 배포 최적화"
            ),
        )
    ]
)


class TestEditEndpointSuccess:
    """이력서 수정 엔드포인트 성공 테스트"""

    @pytest.mark.asyncio
    async def test_edit_success(self, async_client):
        """정상 수정 요청 시 jobId 즉시 반환"""
        with patch(
            "app.api.v2.resume_edit._run_edit_and_callback",
            new_callable=AsyncMock,
        ):
            response = await async_client.post(
                "/api/v2/resume/edit",
                json=SAMPLE_EDIT_REQUEST,
            )

        assert response.status_code == 200
        data = response.json()
        assert "jobId" in data


class TestEditEndpointFailure:
    """이력서 수정 엔드포인트 실패 테스트"""

    @pytest.mark.asyncio
    async def test_edit_llm_failure(self, async_client):
        """LLM 실패 시에도 jobId 반환 후 실패 콜백 페이로드 생성"""
        from app.api.v2.resume_edit import _build_callback_payload

        with patch(
            "app.api.v2.resume_edit._run_edit_and_callback",
            new_callable=AsyncMock,
        ):
            response = await async_client.post(
                "/api/v2/resume/edit",
                json=SAMPLE_EDIT_REQUEST,
            )

        assert response.status_code == 200
        assert "jobId" in response.json()

        payload = _build_callback_payload(
            response.json()["jobId"], None, "LLM API 오류: HTTP 500"
        )
        assert payload["status"] == "failed"
        assert payload["error"]["code"] == ErrorCode.EDIT_FAILED
        assert "LLM API" in payload["error"]["message"]

    @pytest.mark.asyncio
    async def test_edit_timeout(self, async_client):
        """타임아웃 시에도 jobId 반환 후 실패 콜백 페이로드 생성"""
        from app.api.v2.resume_edit import _build_callback_payload

        with patch(
            "app.api.v2.resume_edit._run_edit_and_callback",
            new_callable=AsyncMock,
        ):
            response = await async_client.post(
                "/api/v2/resume/edit",
                json=SAMPLE_EDIT_REQUEST,
            )

        assert response.status_code == 200
        assert "jobId" in response.json()

        payload = _build_callback_payload(
            response.json()["jobId"], None, "워크플로우 타임아웃: 180초 초과"
        )
        assert payload["status"] == "failed"
        assert "타임아웃" in payload["error"]["message"]


class TestEditEndpointValidation:
    """이력서 수정 엔드포인트 유효성 검증 테스트"""

    @pytest.mark.asyncio
    async def test_empty_request_message(self, async_client):
        """빈 requestMessage 시 422"""
        invalid_request = {
            **SAMPLE_EDIT_REQUEST,
            "requestMessage": "",
        }
        response = await async_client.post(
            "/api/v2/resume/edit",
            json=invalid_request,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_projects(self, async_client):
        """projects 누락 시 422"""
        invalid_request = {
            "resumeId": 1,
            "content": {"projects": []},
            "requestMessage": "수정해줘",
        }
        response = await async_client.post(
            "/api/v2/resume/edit",
            json=invalid_request,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_content(self, async_client):
        """content 필드 누락 시 422"""
        invalid_request = {
            "resumeId": 1,
            "requestMessage": "수정해줘",
        }
        response = await async_client.post(
            "/api/v2/resume/edit",
            json=invalid_request,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_resume_id(self, async_client):
        """resumeId가 0 이하일 때 422"""
        invalid_request = {
            **SAMPLE_EDIT_REQUEST,
            "resumeId": 0,
        }
        response = await async_client.post(
            "/api/v2/resume/edit",
            json=invalid_request,
        )

        assert response.status_code == 422


class TestEditWorkflow:
    """이력서 수정 워크플로우 테스트"""

    @pytest.mark.asyncio
    async def test_edit_node_success(self):
        """edit_node 정상 동작"""
        from app.domain.resume.edit_workflow import edit_node

        state = {
            "resume_json": '{"projects": []}',
            "message": "수정 요청",
            "session_id": None,
            "retry_count": 0,
        }

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=SAMPLE_EDITED_OUTPUT
        )

        with patch("app.infra.llm.client.get_generator_llm", return_value=mock_llm):
            result = await edit_node(state)

        assert "error_code" not in result or not result.get("error_code")
        assert result["edited_resume"] == SAMPLE_EDITED_OUTPUT

    @pytest.mark.asyncio
    async def test_evaluate_node_pass(self):
        """evaluate_node 평가 통과"""
        from app.domain.resume.edit_workflow import evaluate_node

        eval_result = EvaluationOutput(
            result="pass",
            violated_rule=None,
            violated_item=None,
            feedback="모든 규칙 준수",
        )

        state = {
            "resume_json": '{"projects": []}',
            "message": "수정 요청",
            "session_id": None,
            "retry_count": 0,
            "edited_resume": SAMPLE_EDITED_OUTPUT,
        }

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=eval_result)

        with patch("app.infra.llm.client.get_evaluator_llm", return_value=mock_llm):
            result = await evaluate_node(state)

        assert result["evaluation"] == "pass"

    @pytest.mark.asyncio
    async def test_evaluate_node_fail(self):
        """evaluate_node 평가 실패"""
        from app.domain.resume.edit_workflow import evaluate_node

        eval_result = EvaluationOutput(
            result="fail",
            violated_rule=5,
            violated_item="~했습니다",
            feedback="금지 어미 사용",
        )

        state = {
            "resume_json": '{"projects": []}',
            "message": "수정 요청",
            "session_id": None,
            "retry_count": 0,
            "edited_resume": SAMPLE_EDITED_OUTPUT,
        }

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=eval_result)

        with patch("app.infra.llm.client.get_evaluator_llm", return_value=mock_llm):
            result = await evaluate_node(state)

        assert result["evaluation"] == "fail"
        assert result["evaluation_feedback"] == "금지 어미 사용"


class TestEditAgent:
    """이력서 수정 에이전트 테스트"""

    @pytest.mark.asyncio
    async def test_run_edit_agent_success(self):
        """에이전트 정상 실행"""
        from app.domain.resume.edit_agent import run_edit_agent

        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(
            return_value={
                "edited_resume": SAMPLE_EDITED_OUTPUT,
                "evaluation": "pass",
                "retry_count": 0,
            }
        )

        with (
            patch(
                "app.domain.resume.edit_agent._edit_workflow",
                mock_workflow,
            ),
            patch(
                "app.domain.resume.edit_agent.get_langfuse_handler",
                return_value=None,
            ),
        ):
            result, error = await run_edit_agent(
                resume_json='{"projects": []}',
                message="수정 요청",
            )

        assert result == SAMPLE_EDITED_OUTPUT
        assert error is None

    @pytest.mark.asyncio
    async def test_run_edit_agent_error(self):
        """에이전트 에러 상태 반환"""
        from app.domain.resume.edit_agent import run_edit_agent

        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(
            return_value={
                "error_code": ErrorCode.EDIT_FAILED,
                "error_message": "이력서 수정 실패",
            }
        )

        with (
            patch(
                "app.domain.resume.edit_agent._edit_workflow",
                mock_workflow,
            ),
            patch(
                "app.domain.resume.edit_agent.get_langfuse_handler",
                return_value=None,
            ),
        ):
            result, error = await run_edit_agent(
                resume_json='{"projects": []}',
                message="수정 요청",
            )

        assert result is None
        assert error == "이력서 수정 실패"

    @pytest.mark.asyncio
    async def test_run_edit_agent_timeout(self):
        """에이전트 타임아웃"""
        from app.domain.resume.edit_agent import run_edit_agent

        mock_workflow = MagicMock()
        mock_workflow.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

        with (
            patch(
                "app.domain.resume.edit_agent._edit_workflow",
                mock_workflow,
            ),
            patch(
                "app.domain.resume.edit_agent.get_langfuse_handler",
                return_value=None,
            ),
        ):
            result, error = await run_edit_agent(
                resume_json='{"projects": []}',
                message="수정 요청",
            )

        assert result is None
        assert "타임아웃" in error
