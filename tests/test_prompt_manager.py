"""Langfuse prompt_manager fallback 동작 테스트"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import LLMError


class TestGetPromptFallback:
    """get_prompt에서 _get_client 실패 시 fallback 동작 검증"""

    def test_falls_back_when_client_raises_llm_error(self):
        """API 키 미설정으로 LLMError 발생 시 로컬 fallback 사용"""
        with (
            patch(
                "app.infra.langfuse.prompt_manager._get_client",
                side_effect=LLMError(detail="Langfuse API 키가 설정되지 않음"),
            ),
            patch(
                "app.infra.langfuse.prompt_manager._get_local_fallback",
                return_value="fallback-prompt",
            ) as mock_fallback,
        ):
            from app.infra.langfuse.prompt_manager import get_prompt

            result = get_prompt("interview-technical-system", position="backend")

            mock_fallback.assert_called_once_with(
                "interview-technical-system", position="backend"
            )
            assert result == "fallback-prompt"

    def test_falls_back_when_client_raises_connection_error(self):
        """네트워크 오류로 ConnectionError 발생 시 로컬 fallback 사용"""
        with (
            patch(
                "app.infra.langfuse.prompt_manager._get_client",
                side_effect=ConnectionError("Langfuse 서버 연결 실패"),
            ),
            patch(
                "app.infra.langfuse.prompt_manager._get_local_fallback",
                return_value="fallback-prompt",
            ) as mock_fallback,
        ):
            from app.infra.langfuse.prompt_manager import get_prompt

            result = get_prompt("chat-technical-system")

            mock_fallback.assert_called_once_with("chat-technical-system")
            assert result == "fallback-prompt"

    def test_falls_back_when_get_prompt_api_fails(self):
        """클라이언트 정상이지만 get_prompt API 실패 시 fallback"""
        mock_client = MagicMock()
        mock_client.get_prompt.side_effect = Exception("API 호출 실패")

        with (
            patch(
                "app.infra.langfuse.prompt_manager._get_client",
                return_value=mock_client,
            ),
            patch(
                "app.infra.langfuse.prompt_manager._get_local_fallback",
                return_value="fallback-prompt",
            ) as mock_fallback,
        ):
            from app.infra.langfuse.prompt_manager import get_prompt

            result = get_prompt("feedback-technical-system")

            mock_fallback.assert_called_once_with("feedback-technical-system")
            assert result == "fallback-prompt"

    def test_success_with_langfuse(self):
        """Langfuse 정상 동작 시 컴파일된 프롬프트 반환"""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "compiled-prompt"
        mock_client = MagicMock()
        mock_client.get_prompt.return_value = mock_prompt

        with patch(
            "app.infra.langfuse.prompt_manager._get_client",
            return_value=mock_client,
        ):
            from app.infra.langfuse.prompt_manager import get_prompt

            result = get_prompt("interview-technical-system", position="backend")

            mock_client.get_prompt.assert_called_once_with("interview-technical-system")
            mock_prompt.compile.assert_called_once_with(position="backend")
            assert result == "compiled-prompt"

    def test_unknown_name_raises_error_after_client_failure(self):
        """fallback registry에도 없는 이름이면 LLMError 발생"""
        with patch(
            "app.infra.langfuse.prompt_manager._get_client",
            side_effect=LLMError(detail="API 키 미설정"),
        ):
            from app.infra.langfuse.prompt_manager import get_prompt

            with pytest.raises(LLMError) as exc_info:
                get_prompt("nonexistent-prompt-name")
            assert "fallback 없음" in exc_info.value.detail
