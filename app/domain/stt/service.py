from app.core.exceptions import CustomException, ErrorCode
from app.core.logging import get_logger
from app.infra.s3.client import download_file
from app.infra.stt.client import transcribe_audio

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {"wav", "mp3", "webm", "m4a", "ogg", "flac"}


async def transcribe_from_s3(s3_key: str, language: str = "ko") -> str:
    """S3의 오디오 파일을 다운로드하여 텍스트로 변환"""
    filename = s3_key.rsplit("/", maxsplit=1)[-1]
    extension = filename.rsplit(".", maxsplit=1)[-1].lower() if "." in filename else ""

    if extension not in ALLOWED_EXTENSIONS:
        raise CustomException(
            status_code=400,
            error_code=ErrorCode.INVALID_AUDIO_FORMAT,
            message="지원하지 않는 오디오 형식입니다",
            detail=f"허용 형식: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    logger.debug("STT 변환 시작", s3_key=s3_key, language=language)

    file_content = await download_file(s3_key)
    text = await transcribe_audio(file_content, filename, language)

    logger.debug("STT 변환 완료", s3_key=s3_key, text_length=len(text))
    return text
