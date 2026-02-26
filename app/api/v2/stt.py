from fastapi import APIRouter, Request

from app.api.v2.schemas.stt import STTErrorResponse, TranscriptionRequest, TranscriptionResponse
from app.core.exceptions import CustomException, ErrorCode
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.domain.stt.service import transcribe_from_s3

router = APIRouter(prefix="/stt", tags=["v2"])
logger = get_logger(__name__)


@router.post("/transcribe", response_model=TranscriptionResponse, summary="음성을 텍스트로 변환")
@limiter.limit("20/minute")
async def transcribe(
    request: Request,
    body: TranscriptionRequest,
) -> TranscriptionResponse:
    """S3에 저장된 오디오 파일을 텍스트로 변환

    분당 20회 요청 제한이 적용됩니다
    """
    logger.info("STT 변환 요청", s3_key=body.s3_key, language=body.language)

    try:
        text = await transcribe_from_s3(body.s3_key, body.language)
    except CustomException:
        raise
    except Exception as e:
        logger.error("STT 변환 실패", error=str(e), exc_info=True)
        return TranscriptionResponse(
            status="failed",
            error=STTErrorResponse(
                code=ErrorCode.STT_API_ERROR,
                message="음성 변환 처리 중 오류가 발생했습니다",
            ),
        )

    logger.info("STT 변환 성공", s3_key=body.s3_key)
    return TranscriptionResponse(
        status="success",
        text=text,
    )
