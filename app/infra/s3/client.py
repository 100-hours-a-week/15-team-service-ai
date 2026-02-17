import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


async def download_file(s3_key: str) -> bytes:
    """S3에서 파일 다운로드"""
    session = aioboto3.Session()

    try:
        async with session.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        ) as client:
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
