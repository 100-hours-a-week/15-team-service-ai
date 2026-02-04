"""
structlog 기반 로깅 설정

- 개발 환경: 컬러풀한 콘솔 출력
- 프로덕션 환경: JSON 형식 출력
- 컨텍스트 자동 주입: request_id, job_id
"""

import logging
import re
import sys

import structlog

from app.core.config import settings
from app.core.context import get_job_id, get_request_id

SENSITIVE_PATTERNS = [
    (re.compile(r"(token=)[^&\s]+", re.IGNORECASE), r"\1***"),
    (re.compile(r"(Bearer\s+)[^\s]+", re.IGNORECASE), r"\1***"),
    (re.compile(r"(api[_-]?key=)[^&\s]+", re.IGNORECASE), r"\1***"),
    (re.compile(r"(password=)[^&\s]+", re.IGNORECASE), r"\1***"),
]


def _mask_sensitive_data(value: str) -> str:
    """민감한 정보 마스킹"""
    for pattern, replacement in SENSITIVE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def add_context_processor(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    """request_id와 job_id를 로그에 자동 주입"""
    request_id = get_request_id()
    job_id = get_job_id()

    if request_id:
        event_dict["request_id"] = request_id
    if job_id:
        event_dict["job_id"] = job_id

    return event_dict


def mask_sensitive_processor(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    """프로덕션에서 민감한 정보 마스킹"""
    if not settings.is_production:
        return event_dict

    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = _mask_sensitive_data(value)

    return event_dict


def setup_logging(level: str | None = None) -> None:
    """structlog 설정 초기화"""
    if level is None:
        level = settings.log_level
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_context_processor,
        mask_sensitive_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.is_production:
        shared_processors.append(structlog.processors.format_exc_info)
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logging.getLogger(logger_name).handlers.clear()

    noisy_loggers = [
        "httpcore",
        "httpx",
        "urllib3",
        "langfuse",
        "langchain",
        "langgraph",
        "openai",
        "anyio",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """structlog 로거 반환"""
    return structlog.get_logger(name)
