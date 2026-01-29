"""app/main.py 테스트"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class TestHealthCheck:
    """헬스체크 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_health_check_returns_up(self):
        """헬스체크 엔드포인트가 정상 응답을 반환"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "UP"}


class TestAppConfiguration:
    """앱 설정 테스트"""

    def test_app_has_correct_title(self):
        """앱 제목이 올바르게 설정됨"""
        assert app.title == "Dev Experience Extractor"

    def test_app_has_correct_version(self):
        """앱 버전이 올바르게 설정됨"""
        assert app.version == "1.0.0"

    def test_router_is_included(self):
        """API 라우터가 포함됨"""
        routes = [route.path for route in app.routes]
        assert "/health" in routes
