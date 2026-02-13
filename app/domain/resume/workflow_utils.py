import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


def has_error(state: dict[str, Any], caller: str) -> bool:
    """에러 상태 확인"""
    if state.get("error_code"):
        logger.warning("에러 상태 감지, 종료", caller=caller, error_code=state.get("error_code"))
        return True
    return False


def should_evaluate(state: dict[str, Any]) -> str:
    """에러 확인: 에러 있으면 종료, 없으면 평가로"""
    return "end" if has_error(state, "should_evaluate") else "evaluate"


def make_should_retry(
    max_retries: int,
    retry_node: str,
) -> Callable[[dict[str, Any]], str]:
    """should_retry 라우터 함수 생성

    Args:
        max_retries: 최대 재시도 횟수
        retry_node: 재시도 시 이동할 노드 이름
    """

    def should_retry(state: dict[str, Any]) -> str:
        if has_error(state, "should_retry"):
            return "end"

        evaluation = state.get("evaluation", "pass")
        retry_count = state.get("retry_count", 0)

        if evaluation == "pass":
            logger.info("should_retry: 평가 통과, 종료")
            return "end"

        if retry_count >= max_retries:
            logger.warning("should_retry: 최대 재시도 도달, 종료")
            return "end"

        logger.info("should_retry: 재시도 필요", retry_count=retry_count)
        return retry_node

    return should_retry


async def evaluate_with_fallback(
    state: dict[str, Any],
    evaluate_fn: Callable[[], Awaitable[Any]],
    node_name: str = "evaluate_node",
) -> dict[str, Any]:
    """평가 실행 후 실패 시 pass로 폴백

    Args:
        state: 워크플로우 상태
        evaluate_fn: 평가 실행 함수, result와 feedback 속성을 가진 객체 반환
        node_name: 로그에 표시할 노드 이름
    """
    logger.info("평가 노드 시작", node=node_name)
    start_time = time.monotonic()

    try:
        evaluation = await evaluate_fn()

        elapsed = time.monotonic() - start_time
        logger.info(
            "평가 노드 완료",
            node=node_name,
            result=evaluation.result,
            elapsed_s=round(elapsed, 1),
        )

        return {
            **state,
            "evaluation": evaluation.result,
            "evaluation_feedback": evaluation.feedback,
        }

    except httpx.TimeoutException as e:
        elapsed = time.monotonic() - start_time
        logger.error(
            "타임아웃으로 평가 건너뜀",
            node=node_name,
            error=str(e),
            elapsed_s=round(elapsed, 1),
        )

    except httpx.ConnectError as e:
        elapsed = time.monotonic() - start_time
        logger.error(
            "Gemini 연결 실패로 평가 건너뜀",
            node=node_name,
            error=str(e),
            elapsed_s=round(elapsed, 1),
        )

    except httpx.HTTPStatusError as e:
        elapsed = time.monotonic() - start_time
        logger.error(
            "Gemini API 오류로 평가 건너뜀",
            node=node_name,
            status=e.response.status_code,
            elapsed_s=round(elapsed, 1),
        )

    except (ValueError, KeyError, TypeError) as e:
        elapsed = time.monotonic() - start_time
        logger.error(
            "데이터 파싱 오류로 평가 건너뜀",
            node=node_name,
            error=str(e),
            elapsed_s=round(elapsed, 1),
        )

    return {
        **state,
        "evaluation": "pass",
        "evaluation_feedback": "",
    }
