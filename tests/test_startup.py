import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_app_startup_lifespan():
    """
    앱의 lifespan (스타트업 로직)이 정상적으로 실행되는지 확인합니다.
    DB 경로 미존재 등의 설정 오류가 있으면 이 단계에서 실패합니다.
    """
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "UP"}
    except Exception as e:
        pytest.fail(f"App failed to start during lifespan: {e}")
