import asyncio

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_session = aioboto3.Session()
_s3_client = None
_s3_client_ctx = None
_s3_lock = asyncio.Lock()


async def _get_s3_client():
    """S3 클라이언트 지연 초기화 싱글턴"""
    global _s3_client, _s3_client_ctx
    if _s3_client is not None:
        return _s3_client
    async with _s3_lock:
        if _s3_client is None:
            if not settings.aws_access_key_id or not settings.aws_secret_access_key:
                logger.error("AWS 자격증명 미설정 — access_key_id 또는 secret_access_key 없음")
                raise RuntimeError("AWS 자격증명이 설정되지 않음")
            _s3_client_ctx = _session.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            _s3_client = await _s3_client_ctx.__aenter__()
    return _s3_client


async def close_s3_client() -> None:
    """S3 클라이언트 종료 - lifespan에서 호출"""
    global _s3_client, _s3_client_ctx
    if _s3_client_ctx:
        await _s3_client_ctx.__aexit__(None, None, None)
        _s3_client = None
        _s3_client_ctx = None


async def download_file(s3_key: str) -> bytes:
    """S3에서 파일 다운로드"""
    try:
        client = await _get_s3_client()
        response = await client.get_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
        )
        data = await response["Body"].read()
        logger.debug("S3 파일 다운로드 완료", s3_key=s3_key, size=len(data))
        return data
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            logger.warning("S3 파일 없음", s3_key=s3_key)
            raise
        logger.error("S3 다운로드 실패", s3_key=s3_key, error_code=error_code, exc_info=True)
        raise
    except Exception:
        logger.error("S3 다운로드 중 예외 발생", s3_key=s3_key, exc_info=True)
        raise
