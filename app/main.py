from fastapi import FastAPI

from app.api.routers import api_router


app = FastAPI(title="Dev Experience Extractor", version="1.0.0")

app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "UP"}
