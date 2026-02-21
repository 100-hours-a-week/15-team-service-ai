import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routers import api_router, api_v2_router
from app.api.v1.resume import get_background_tasks as get_v1_tasks
from app.api.v2.resume_edit import get_background_tasks as get_v2_edit_tasks
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.limiter import limiter
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.infra.github.client import close_client as close_github_client
from app.infra.llm.client import setup_langfuse_env

setup_logging()
setup_langfuse_env()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 이벤트 관리"""
    async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
        app.state.checkpointer = checkpointer
        logger.info("AsyncSqliteSaver 체크포인터 초기화 완료")
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
        await close_github_client()


app = FastAPI(
    title="Dev Experience Extractor",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)

register_exception_handlers(app)
app.include_router(api_router)
app.include_router(api_v2_router)


@app.get("/health")
async def health_check():
    return {"status": "UP"}
