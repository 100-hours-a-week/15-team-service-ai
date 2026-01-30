"""이력서 API 엔드포인트 테스트"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class TestGenerateResumeEndpoint:
    """POST /api/v1/resume/generate 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_generate_returns_job_id(self):
        """정상 요청 시 jobId 반환"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.resume._run_agent_and_callback", new_callable=AsyncMock):
                response = await client.post(
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
    async def test_generate_with_company(self):
        """회사명 포함 요청 시 정상 동작"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.v1.resume._run_agent_and_callback", new_callable=AsyncMock):
                response = await client.post(
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
    async def test_generate_empty_repo_urls_returns_422(self):
        """repo_urls 빈 배열 시 422 에러"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/resume/generate",
                json={
                    "repoUrls": [],
                    "position": "백엔드 개발자",
                    "githubToken": "test-token-123",
                },
            )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("최소 1개" in str(err) for err in detail)

    @pytest.mark.asyncio
    async def test_generate_too_many_repos_returns_422(self):
        """repo_urls 10개 초과 시 422 에러"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            repos = [f"https://github.com/user/repo{i}" for i in range(11)]
            response = await client.post(
                "/api/v1/resume/generate",
                json={
                    "repoUrls": repos,
                    "position": "백엔드 개발자",
                    "githubToken": "test-token-123",
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_empty_position_returns_422(self):
        """position 빈 문자열 시 422 에러"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/resume/generate",
                json={
                    "repoUrls": ["https://github.com/testuser/testrepo"],
                    "position": "",
                    "githubToken": "test-token-123",
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_missing_github_token_returns_422(self):
        """github_token 누락 시 422 에러"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/resume/generate",
                json={
                    "repoUrls": ["https://github.com/testuser/testrepo"],
                    "position": "백엔드 개발자",
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_invalid_github_url_returns_422(self):
        """잘못된 GitHub URL 형식 시 422 에러"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/resume/generate",
                json={
                    "repoUrls": ["https://gitlab.com/testuser/testrepo"],
                    "position": "백엔드 개발자",
                    "githubToken": "test-token-123",
                },
            )

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert any("GitHub URL" in str(err) for err in detail)

    @pytest.mark.asyncio
    async def test_generate_invalid_url_format_returns_422(self):
        """URL 형식 오류 시 422 에러"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/resume/generate",
                json={
                    "repoUrls": ["not-a-valid-url"],
                    "position": "백엔드 개발자",
                    "githubToken": "test-token-123",
                },
            )

        assert response.status_code == 422


class TestHealthEndpoint:
    """GET /health 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_health_returns_up(self):
        """헬스체크 정상 응답"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "UP"}
