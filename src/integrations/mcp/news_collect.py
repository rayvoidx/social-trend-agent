from __future__ import annotations

"""
뉴스 데이터 수집용 MCP 클라이언트 래퍼

- 외부 MCP 서버(brave-search 등)를 통해서만 뉴스/웹 문서를 검색합니다.
- NewsAPI / Naver News API와 같은 직접 HTTP 기반 수집은 사용하지 않습니다.
"""

import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

from src.integrations.mcp.servers.mcp_client import call_mcp_tool

logger = logging.getLogger(__name__)


def _run_coro(coro_factory):
    """
    동기 함수에서 async 함수를 호출하기 위한 헬퍼.

    - 현재 스레드에서 이벤트 루프가 실행 중이면(예: FastAPI/uvicorn), 같은 스레드에서
      asyncio.run()/run_until_complete()를 호출할 수 없어 RuntimeError가 발생합니다.
    - 이 경우 별도 스레드에서 asyncio.run()으로 실행하여 충돌을 방지합니다.
    """
    try:
        # If a loop is running in this thread, this will succeed.
        loop = asyncio.get_running_loop()
        if loop.is_running():
            result_holder: Dict[str, Any] = {}
            error_holder: Dict[str, BaseException] = {}

            def _runner():
                try:
                    result_holder["result"] = asyncio.run(coro_factory())
                except BaseException as e:  # propagate exact exception type
                    error_holder["error"] = e

            t = threading.Thread(target=_runner, daemon=True)
            t.start()
            t.join()

            if "error" in error_holder:
                raise error_holder["error"]
            return result_holder.get("result")
    except RuntimeError:
        # No running loop in this thread
        pass

    return asyncio.run(coro_factory())


def search_news_via_mcp(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 20,
    server_name: str = "brave-search",
    tool_name: str = "search",
) -> List[Dict[str, Any]]:
    """
    MCP 서버(예: brave-search)를 통해 뉴스/웹 검색을 수행합니다.

    MCP 서버와 툴 이름은 실제 서버 구현에 따라 다를 수 있으므로,
    필요시 server_name / tool_name을 조정해야 합니다.
    """

    async def _call() -> Dict[str, Any]:
        return await call_mcp_tool(
            server_name,
            tool_name,
            {
                "query": query,
                "count": max_results,
                "time_window": time_window,
                "language": language,
            },
        )

    try:
        result = _run_coro(_call) or {}
    except Exception as e:
        logger.error(f"News MCP call failed: {e}")
        return []

    # 기사 리스트 후보 키들
    articles = (
        result.get("articles")
        or result.get("items")
        or result.get("results")
        or []
    )

    out: List[Dict[str, Any]] = []
    for a in articles[:max_results]:
        out.append(
            {
                "title": a.get("title", ""),
                "description": a.get("description", "") or a.get("snippet", ""),
                "url": a.get("url", ""),
                "source": {"name": a.get("source") or a.get("site_name", "MCP News")},
                "publishedAt": a.get("publishedAt") or a.get("published_at"),
                "content": a.get("content", ""),
            }
        )

    return out