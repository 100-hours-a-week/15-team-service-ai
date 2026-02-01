"""이력서 API 엔드포인트 테스트"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.api.v1.resume import _build_callback_payload, _send_callback_with_retry
from app.domain.resume.schemas import ProjectInfo, ResumeData


class TestBuildCallbackPayload:
    """_build_callback_payload 함수 테스트"""

    def test_success_payload(self):
        """성공 페이로드 생성"""
        resume_data = ResumeData(
            projects=[
                ProjectInfo(
                    name="Test",
                    repo_url="https://github.com/user/test",
                    description="Test project",
                    tech_stack=["Python"],
                )
            ]
        )

        result = _build_callback_payload("job-123", resume_data, None)

        assert result["jobId"] == "job-123"
        assert result["status"] == "success"
        assert "resume" in result
        assert len(result["resume"]["projects"]) == 1

    def test_error_payload(self):
        """에러 페이로드 생성"""
        result = _build_callback_payload("job-123", None, "Generation failed")

        assert result["jobId"] == "job-123"
        assert result["status"] == "failed"
        assert result["error"]["message"] == "Generation failed"

    def test_error_payload_default_message(self):
        """에러 페이로드 기본 메시지"""
        result = _build_callback_payload("job-123", None, None)

        assert result["status"] == "failed"
        assert "실패" in result["error"]["message"]


class TestSendCallbackWithRetry:
    """_send_callback_with_retry 함수 테스트"""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        """첫 시도에 성공"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await _send_callback_with_retry(
            mock_client, "http://example.com/callback", {"data": "test"}, "job-123"
        )

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_error_status(self, mock_callback_settings):
        """에러 상태 코드에서 재시도"""
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            side_effect=[mock_response_error, mock_response_success]
        )

        result = await _send_callback_with_retry(
            mock_client, "http://example.com/callback", {}, "job-123"
        )

        assert result is True
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_request_error(self, mock_callback_settings):
        """요청 에러에서 재시도"""
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            side_effect=[httpx.RequestError("Connection error"), mock_response_success]
        )

        result = await _send_callback_with_retry(
            mock_client, "http://example.com/callback", {}, "job-123"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """최대 재시도 초과"""
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection error"))

        with patch("app.api.v1.resume.settings") as mock_settings:
            mock_settings.callback_max_retries = 2
            mock_settings.callback_retry_base_delay = 0.01
            mock_settings.ai_callback_secret = "secret"

            result = await _send_callback_with_retry(
                mock_client, "http://example.com/callback", {}, "job-123"
            )

        assert result is False
        assert mock_client.post.call_count == 2


class TestGenerateResumeEndpoint:
    """POST /api/v1/resume/generate 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_generate_returns_job_id(self, async_client):
        """정상 요청 시 jobId 반환"""
        with patch("app.api.v1.resume._run_agent_and_callback", new_callable=AsyncMock):
            response = await async_client.post(
                "/api/v1/resume/generate",
                json={
                    "repoUrls": ["https://github.com/testuser/testrepo"],
                    "position": "백엔드 개발자",
                    "githubToken": "test-token-123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "jobId" in data
        assert isinstance(data["jobId"], str)
        assert len(data["jobId"]) == 36

    @pytest.mark.asyncio
    async def test_generate_with_company(self, async_client):
        """회사명 포함 요청 시 정상 동작"""
        with patch("app.api.v1.resume._run_agent_and_callback", new_callable=AsyncMock):
            response = await async_client.post(
                "/api/v1/resume/generate",
                json={
                    "repoUrls": ["https://github.com/testuser/testrepo"],
                    "position": "백엔드 개발자",
                    "company": "테스트회사",
                    "githubToken": "test-token-123",
                },
            )

        assert response.status_code == 200
        assert "jobId" in response.json()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload,error_check",
        [
            (
                {
                    "repoUrls": [],
                    "position": "백엔드 개발자",
                    "githubToken": "test-token",
                },
                lambda d: any("최소 1개" in str(e) for e in d),
            ),
            (
                {
                    "repoUrls": [f"https://github.com/user/repo{i}" for i in range(11)],
                    "position": "백엔드 개발자",
                    "githubToken": "test-token",
                },
                None,
            ),
            (
                {
                    "repoUrls": ["https://github.com/testuser/testrepo"],
                    "position": "",
                    "githubToken": "test-token",
                },
                None,
            ),
            (
                {
                    "repoUrls": ["https://github.com/testuser/testrepo"],
                    "position": "백엔드 개발자",
                },
                None,
            ),
            (
                {
                    "repoUrls": ["https://gitlab.com/testuser/testrepo"],
                    "position": "백엔드 개발자",
                    "githubToken": "test-token",
                },
                lambda d: any("GitHub URL" in str(e) for e in d),
            ),
            (
                {
                    "repoUrls": ["not-a-valid-url"],
                    "position": "백엔드 개발자",
                    "githubToken": "test-token",
                },
                None,
            ),
        ],
        ids=[
            "empty_repo_urls",
            "too_many_repos",
            "empty_position",
            "missing_github_token",
            "invalid_github_url",
            "invalid_url_format",
        ],
    )
    async def test_generate_validation_errors(self, async_client, payload, error_check):
        """422 유효성 검사 에러 테스트"""
        response = await async_client.post("/api/v1/resume/generate", json=payload)

        assert response.status_code == 422
        if error_check:
            detail = response.json()["detail"]
            assert error_check(detail)


class TestHealthEndpoint:
    """GET /health 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_health_returns_up(self, async_client):
        """헬스체크 정상 응답"""
        response = await async_client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "UP"}
