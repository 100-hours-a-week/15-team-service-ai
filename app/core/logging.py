import logging
import re
import sys

from app.core.config import settings


class SensitiveDataFilter(logging.Filter):
    """로그에서 민감한 정보 마스킹"""

    PATTERNS = [
        (re.compile(r"(token=)[^&\s]+", re.IGNORECASE), r"\1***"),
        (re.compile(r"(Bearer\s+)[^\s]+", re.IGNORECASE), r"\1***"),
        (re.compile(r"(api[_-]?key=)[^&\s]+", re.IGNORECASE), r"\1***"),
        (re.compile(r"(password=)[^&\s]+", re.IGNORECASE), r"\1***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if not settings.is_production:
            return True

        if record.args:
            record.args = tuple(self._mask_value(arg) for arg in record.args)

        record.msg = self._mask_value(record.msg)
        return True

    def _mask_value(self, value):
        if not isinstance(value, str):
            return value

        for pattern, replacement in self.PATTERNS:
            value = pattern.sub(replacement, value)
        return value


def setup_logging(level: str | None = None):
    if level is None:
        level = settings.log_level
    log_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger("app")
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
