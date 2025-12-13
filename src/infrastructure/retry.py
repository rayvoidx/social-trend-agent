"""
견고한 API 호출을 위한 재시도 및 백오프 유틸리티
"""
import time
import functools
from typing import Callable, Any, Optional, Tuple, Type
import logging

from src.infrastructure.timeout import run_with_timeout, HardTimeoutError

logger = logging.getLogger(__name__)

def backoff_retry(
    max_retries: int = 5,
    backoff_base: float = 2.0,
    backoff_factor: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    지수 백오프 재시도 데코레이터

    Args:
        max_retries: 최대 재시도 횟수 (기본값: 5)
        backoff_base: 지수 백오프의 기저 (기본값: 2.0)
        backoff_factor: 백오프 배수 (기본값: 1.0)
        exceptions: 캐치할 예외 타입 튜플
        on_retry: 각 재시도마다 호출되는 선택적 콜백 함수

    백오프 공식: backoff_factor * (backoff_base ** retry_count)
    예시: 1 * (2 ** 0) = 1초, 1 * (2 ** 1) = 2초, 1 * (2 ** 2) = 4초, ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Plan-aware dynamic overrides (runtime)
            plan_rp = kwargs.pop("__plan_retry_policy", None)
            plan_timeout = kwargs.pop("__plan_timeout_seconds", None)
            _ = kwargs.pop("__plan_step_id", None)  # reserved for logging in future

            dyn_max_retries = max_retries
            dyn_backoff_factor = backoff_factor
            dyn_backoff_base = backoff_base
            if isinstance(plan_rp, dict):
                mr = plan_rp.get("max_retries")
                bo = plan_rp.get("backoff_seconds")
                try:
                    if isinstance(mr, int):
                        dyn_max_retries = max(0, min(5, mr))
                except Exception:
                    pass
                # Map backoff_seconds to backoff_factor when base is 2**attempt.
                # We interpret bo as initial delay.
                try:
                    if isinstance(bo, (int, float)):
                        dyn_backoff_factor = float(bo)
                except Exception:
                    pass

            last_exception = None

            for attempt in range(dyn_max_retries + 1):
                try:
                    # Hard timeout (process-first; thread fallback) if provided.
                    if isinstance(plan_timeout, int) and plan_timeout > 0:
                        result = run_with_timeout(func, *args, timeout_seconds=plan_timeout, prefer_process=True, **kwargs)
                    else:
                        result = func(*args, **kwargs)

                    # Log success after retry
                    if attempt > 0:
                        logger.info(
                            f"{func.__name__} succeeded after {attempt} retries"
                        )

                    return result

                except HardTimeoutError as e:
                    last_exception = e
                    if attempt >= dyn_max_retries:
                        logger.error(
                            f"{func.__name__} hard-timeout after {dyn_max_retries} retries: {e}"
                        )
                        break
                    backoff_time = dyn_backoff_factor * (dyn_backoff_base ** attempt)
                    logger.warning(
                        f"{func.__name__} hard-timeout (attempt {attempt + 1}/{dyn_max_retries}). "
                        f"Retrying in {backoff_time:.1f}s..."
                    )
                    time.sleep(backoff_time)
                except exceptions as e:
                    last_exception = e

                    # Don't retry on last attempt
                    if attempt >= dyn_max_retries:
                        logger.error(
                            f"{func.__name__} failed after {dyn_max_retries} retries: {e}"
                        )
                        break

                    # Calculate backoff
                    backoff_time = dyn_backoff_factor * (dyn_backoff_base ** attempt)

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{dyn_max_retries} failed: {e}. "
                        f"Retrying in {backoff_time:.1f}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt + 1)

                    # Wait before retry
                    time.sleep(backoff_time)
            # All retries exhausted
            raise last_exception

        return wrapper
    return decorator


class RetryConfig:
    """재시도 동작을 위한 설정"""

    def __init__(
        self,
        max_retries: int = 5,
        backoff_base: float = 2.0,
        backoff_factor: float = 1.0,
        timeout: float = 30.0
    ):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_factor = backoff_factor
        self.timeout = timeout


# Predefined retry configs
RETRY_CONFIG_AGGRESSIVE = RetryConfig(
    max_retries=3,
    backoff_base=1.5,
    backoff_factor=0.5
)

RETRY_CONFIG_DEFAULT = RetryConfig(
    max_retries=5,
    backoff_base=2.0,
    backoff_factor=1.0
)

RETRY_CONFIG_CONSERVATIVE = RetryConfig(
    max_retries=7,
    backoff_base=2.0,
    backoff_factor=2.0
)


def retry_on_rate_limit(max_retries: int = 3):
    """
    API 제한 에러를 위한 특수 재시도 데코레이터

    일반적인 API 제한 상태 코드: 429, 503
    """
    import requests

    def should_retry(e: Exception) -> bool:
        if isinstance(e, requests.exceptions.HTTPError):
            return e.response.status_code in [429, 503]
        return False

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not should_retry(e) or attempt >= max_retries:
                        raise

                    # Exponential backoff for rate limits
                    backoff_time = 2 ** attempt
                    logger.warning(
                        f"Rate limit hit. Retrying in {backoff_time}s... "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(backoff_time)

            # Should never reach here
            raise RuntimeError("Retry logic error")

        return wrapper
    return decorator


# Example usage:
if __name__ == "__main__":
    import random

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    @backoff_retry(max_retries=3, backoff_factor=0.5)
    def flaky_api_call():
        """Simulates a flaky API call"""
        if random.random() < 0.7:  # 70% failure rate
            raise ConnectionError("API temporarily unavailable")
        return {"status": "success"}

    try:
        result = flaky_api_call()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Failed: {e}")
