from fastapi import FastAPI

from app.api.routers import api_router
from app.core.exceptions import register_exception_handlers


app = FastAPI(title="Dev Experience Extractor", version="1.0.0")

register_exception_handlers(app)
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "UP"}
