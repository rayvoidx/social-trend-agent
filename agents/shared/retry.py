"""
Retry and backoff utilities for robust API calls
"""
import time
import functools
from typing import Callable, Any, Optional, Tuple, Type
import logging

logger = logging.getLogger(__name__)


def backoff_retry(
    max_retries: int = 5,
    backoff_base: float = 2.0,
    backoff_factor: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator for exponential backoff retry

    Args:
        max_retries: Maximum number of retries (default: 5)
        backoff_base: Base for exponential backoff (default: 2.0)
        backoff_factor: Multiplier for backoff (default: 1.0)
        exceptions: Tuple of exception types to catch
        on_retry: Optional callback function called on each retry

    Backoff formula: backoff_factor * (backoff_base ** retry_count)
    Example: 1 * (2 ** 0) = 1s, 1 * (2 ** 1) = 2s, 1 * (2 ** 2) = 4s, ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Log success after retry
                    if attempt > 0:
                        logger.info(
                            f"{func.__name__} succeeded after {attempt} retries"
                        )

                    return result

                except exceptions as e:
                    last_exception = e

                    # Don't retry on last attempt
                    if attempt >= max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {e}"
                        )
                        break

                    # Calculate backoff
                    backoff_time = backoff_factor * (backoff_base ** attempt)

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}. "
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
    """Configuration for retry behavior"""

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
    Specialized retry decorator for rate limit errors

    Common rate limit status codes: 429, 503
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
