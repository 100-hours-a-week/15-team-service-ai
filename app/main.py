from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.infra.github.client import close_client as close_github_client

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 이벤트 관리"""
    if settings.is_production:
        errors = settings.validate_for_production()
        if errors:
            raise RuntimeError(f"프로덕션 설정 오류: {', '.join(errors)}")
    yield
    await close_github_client()


app = FastAPI(
    title="Dev Experience Extractor",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)


register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "UP"}
