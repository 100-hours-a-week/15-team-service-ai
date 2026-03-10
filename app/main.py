import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routers import api_router, api_v2_router
from app.api.v1.resume import get_background_tasks as get_v1_tasks
from app.api.v2.resume_edit import get_background_tasks as get_v2_edit_tasks
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.infra.github.client import close_client as close_github_client
from app.infra.llm.base import close_llm_clients
from app.infra.llm.client import setup_langfuse_env
from app.infra.qdrant.client import close_client as close_qdrant_client
from app.infra.s3.client import close_s3_client
from app.infra.stt.client import close_client as close_stt_client

setup_logging()
setup_langfuse_env()
logger = get_logger(__name__)


async def _cleanup_clients():
    """인프라 클라이언트 순차 정리 — 개별 실패가 나머지를 막지 않음"""
    for name, close_fn in [
        ("GitHub", close_github_client),
        ("S3", close_s3_client),
        ("STT", close_stt_client),
    ]:
        try:
            await close_fn()
        except Exception:
            logger.error(f"{name} 클라이언트 정리 실패", exc_info=True)
    for name, close_fn in [
        ("Qdrant", close_qdrant_client),
        ("LLM", close_llm_clients),
    ]:
        try:
            close_fn()
        except Exception:
            logger.error(f"{name} 클라이언트 정리 실패", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 이벤트 관리"""
    async with AsyncSqliteSaver.from_conn_string("data/checkpoints.db") as checkpointer:
        app.state.checkpointer = checkpointer
        logger.info("AsyncSqliteSaver 체크포인터 초기화 완료")
        if settings.is_production:
            missing = settings.validate_for_production()
            if missing:
                logger.warning("프로덕션 필수 설정 누락", missing=missing)
        yield
        tasks = get_v1_tasks() | get_v2_edit_tasks()
        if tasks:
            logger.info("진행 중인 작업 종료 대기", count=len(tasks))
            for task in tasks:
                task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=30.0,
                )
                logger.info("모든 작업 종료 완료")
            except TimeoutError:
                logger.warning("작업 종료 타임아웃 - 30초 초과")
        await _cleanup_clients()


app = FastAPI(
    title="Dev Experience Extractor",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)


app.add_middleware(RequestLoggingMiddleware)

register_exception_handlers(app)
app.include_router(api_router)
app.include_router(api_v2_router)

Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health_check():
    return {"status": "UP"}
