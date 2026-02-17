from fastapi import APIRouter

from app.api.v1.resume import router as resume_router
from app.api.v2.interview import router as interview_router
from app.api.v2.resume_edit import router as resume_edit_router
from app.api.v2.stt import router as stt_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(resume_router)

api_v2_router = APIRouter(prefix="/api/v2")
api_v2_router.include_router(interview_router)
api_v2_router.include_router(resume_edit_router)
api_v2_router.include_router(stt_router)
