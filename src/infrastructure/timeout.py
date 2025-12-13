"""
Hard timeout utilities for sync callables.

Why:
- Thread-based timeouts cannot kill the underlying work reliably.
- Process-based timeouts can terminate the worker process (true hard timeout), but
  require the callable + arguments to be picklable.

Strategy:
- Prefer process mode when possible.
- Fall back to thread mode if process mode fails (pickling, platform constraints).
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple, Dict
import concurrent.futures
import multiprocessing as mp
import os


class HardTimeoutError(TimeoutError):
    pass


def _run_in_process(func: Callable[..., Any], args: Tuple[Any, ...], kwargs: Dict[str, Any], timeout_s: float) -> Any:
    ctx = mp.get_context("spawn")
    q: "mp.Queue" = ctx.Queue()

    def _target(queue: "mp.Queue"):
        try:
            res = func(*args, **kwargs)
            queue.put(("ok", res))
        except Exception as e:  # noqa: BLE001
            queue.put(("err", repr(e)))

    p = ctx.Process(target=_target, args=(q,))
    p.start()
    p.join(timeout=timeout_s)
    if p.is_alive():
        p.terminate()
        p.join(timeout=1)
        raise HardTimeoutError(f"Process timed out after {timeout_s}s")

    if q.empty():
        return None
    status, payload = q.get()
    if status == "ok":
        return payload
    raise RuntimeError(f"Child process error: {payload}")


def _run_in_thread(func: Callable[..., Any], args: Tuple[Any, ...], kwargs: Dict[str, Any], timeout_s: float) -> Any:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(func, *args, **kwargs)
        return fut.result(timeout=timeout_s)


def run_with_timeout(
    func: Callable[..., Any],
    *args: Any,
    timeout_seconds: Optional[int] = None,
    prefer_process: bool = True,
    **kwargs: Any,
) -> Any:
    """
    Execute `func(*args, **kwargs)` with a hard timeout.

    prefer_process:
      - True: try process mode first, then thread fallback
      - False: use thread mode only
    """
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        return func(*args, **kwargs)

    timeout_s = float(timeout_seconds)
    force_process = os.getenv("HARD_TIMEOUT_MODE", "").strip().lower() == "process"
    process_first = prefer_process or force_process

    if process_first:
        try:
            return _run_in_process(func, args, kwargs, timeout_s=timeout_s)
        except Exception:
            # fall back to thread mode (best-effort)
            return _run_in_thread(func, args, kwargs, timeout_s=timeout_s)

    return _run_in_thread(func, args, kwargs, timeout_s=timeout_s)


