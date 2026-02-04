"""
요청 및 작업 컨텍스트 관리 모듈

contextvars를 사용하여 비동기 환경에서도 안전하게 request_id와 job_id를 관리
"""

import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)


def get_request_id() -> str | None:
    """현재 컨텍스트의 request_id 반환"""
    return request_id_var.get()


def set_request_id(request_id: str | None = None) -> str:
    """
    request_id 설정

    인자가 없으면 8자리 UUID 자동 생성
    """
    if request_id is None:
        request_id = uuid.uuid4().hex[:8]
    request_id_var.set(request_id)
    return request_id


def get_job_id() -> str | None:
    """현재 컨텍스트의 job_id 반환"""
    return job_id_var.get()


def set_job_id(job_id: str | None) -> None:
    """job_id 설정"""
    job_id_var.set(job_id)


def clear_context() -> None:
    """모든 컨텍스트 변수 초기화"""
    request_id_var.set(None)
    job_id_var.set(None)
