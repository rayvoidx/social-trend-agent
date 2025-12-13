"""
MCP Utilities
"""

import asyncio
import logging
import functools
from typing import TypeVar, Callable, Any, Awaitable

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Async retry decorator with exponential backoff.

    Usage:
        @retry_with_backoff(retries=3, exceptions=(ConnectionError, TimeoutError))
        async def my_func(): ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Plan-aware runtime overrides
            plan_rp = kwargs.pop("__plan_retry_policy", None)
            plan_timeout = kwargs.pop("__plan_timeout_seconds", None)
            _ = kwargs.pop("__plan_step_id", None)

            dyn_retries = retries
            dyn_initial_delay = initial_delay
            dyn_backoff_factor = backoff_factor
            if isinstance(plan_rp, dict):
                mr = plan_rp.get("max_retries")
                bo = plan_rp.get("backoff_seconds")
                try:
                    if isinstance(mr, int):
                        dyn_retries = max(0, min(5, mr))
                except Exception:
                    pass
                try:
                    if isinstance(bo, (int, float)):
                        dyn_initial_delay = float(bo)
                except Exception:
                    pass

            delay = initial_delay
            last_exception = None

            delay = dyn_initial_delay
            for attempt in range(dyn_retries + 1):
                try:
                    if isinstance(plan_timeout, int) and plan_timeout > 0:
                        return await asyncio.wait_for(
                            func(*args, **kwargs), timeout=float(plan_timeout)
                        )
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == dyn_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {dyn_retries} retries. Last error: {e}"
                        )
                        raise last_exception

                    logger.warning(
                        f"Attempt {attempt + 1}/{dyn_retries} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                    delay *= dyn_backoff_factor

            # Should be unreachable if retries > 0
            if last_exception:
                raise last_exception
            return await func(*args, **kwargs)  # Fallback

        return wrapper

    return decorator
