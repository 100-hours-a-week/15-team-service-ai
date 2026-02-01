"""에이전트 테스트"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.resume.agent import run_resume_agent


class TestRunResumeAgent:
    """run_resume_agent 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success(self, sample_resume_request, sample_resume_data, mock_workflow):
        """정상 실행"""
        mock_workflow.ainvoke.return_value = {"resume_data": sample_resume_data}

        with (
            patch(
                "app.domain.resume.agent.create_resume_workflow",
                return_value=mock_workflow,
            ),
            patch("app.domain.resume.agent.get_langfuse_handler", return_value=None),
        ):
            resume, error = await run_resume_agent(sample_resume_request)

        assert resume == sample_resume_data
        assert error is None

    @pytest.mark.asyncio
    async def test_workflow_error(self, sample_resume_request, mock_workflow):
        """워크플로우 에러 상태 반환"""
        mock_workflow.ainvoke.return_value = {
            "error_code": "GITHUB_API_ERROR",
            "error_message": "API Error",
        }

        with (
            patch(
                "app.domain.resume.agent.create_resume_workflow",
                return_value=mock_workflow,
            ),
            patch("app.domain.resume.agent.get_langfuse_handler", return_value=None),
        ):
            resume, error = await run_resume_agent(sample_resume_request)

        assert resume is None
        assert error == "API Error"

    @pytest.mark.asyncio
    async def test_no_resume_data(self, sample_resume_request, mock_workflow):
        """이력서 데이터 없음"""
        mock_workflow.ainvoke.return_value = {}

        with (
            patch(
                "app.domain.resume.agent.create_resume_workflow",
                return_value=mock_workflow,
            ),
            patch("app.domain.resume.agent.get_langfuse_handler", return_value=None),
        ):
            resume, error = await run_resume_agent(sample_resume_request)

        assert resume is None
        assert error == "이력서 생성 실패"

    @pytest.mark.asyncio
    async def test_timeout(self, sample_resume_request, mock_workflow):
        """타임아웃 발생"""
        mock_workflow.ainvoke.side_effect = asyncio.TimeoutError()

        with (
            patch(
                "app.domain.resume.agent.create_resume_workflow",
                return_value=mock_workflow,
            ),
            patch("app.domain.resume.agent.get_langfuse_handler", return_value=None),
            patch("app.domain.resume.agent.settings") as mock_settings,
        ):
            mock_settings.workflow_timeout = 300
            resume, error = await run_resume_agent(sample_resume_request)

        assert resume is None
        assert "타임아웃" in error

    @pytest.mark.asyncio
    async def test_exception(self, sample_resume_request, mock_workflow):
        """예외 발생"""
        mock_workflow.ainvoke.side_effect = Exception("Unexpected error")

        with (
            patch(
                "app.domain.resume.agent.create_resume_workflow",
                return_value=mock_workflow,
            ),
            patch("app.domain.resume.agent.get_langfuse_handler", return_value=None),
        ):
            resume, error = await run_resume_agent(sample_resume_request)

        assert resume is None
        assert error == "Unexpected error"

    @pytest.mark.asyncio
    async def test_with_langfuse_handler(
        self, sample_resume_request, sample_resume_data, mock_workflow
    ):
        """Langfuse 핸들러 사용"""
        mock_workflow.ainvoke.return_value = {"resume_data": sample_resume_data}
        mock_handler = MagicMock()

        with (
            patch(
                "app.domain.resume.agent.create_resume_workflow",
                return_value=mock_workflow,
            ),
            patch(
                "app.domain.resume.agent.get_langfuse_handler",
                return_value=mock_handler,
            ),
        ):
            resume, error = await run_resume_agent(
                sample_resume_request, session_id="session-123"
            )

        assert resume == sample_resume_data
        mock_workflow.ainvoke.assert_called_once()
        call_args = mock_workflow.ainvoke.call_args
        assert "callbacks" in call_args[1]["config"]
