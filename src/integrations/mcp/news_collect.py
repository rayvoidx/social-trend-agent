from __future__ import annotations

"""
뉴스 데이터 수집용 MCP 클라이언트 래퍼

- 외부 MCP 서버(brave-search 등)를 통해서만 뉴스/웹 문서를 검색합니다.
- MCP 실패 시 직접 API 호출로 폴백합니다.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv(override=True)

from src.integrations.mcp.servers.mcp_client import call_mcp_tool

logger = logging.getLogger(__name__)


def _run_coro(coro):
    """동기 함수에서 async 함수를 호출하기 위한 헬퍼."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _fetch_brave_search_direct(query: str, max_results: int = 20) -> List[Dict[str, Any]]:
    """Brave Search API 직접 호출 (MCP 폴백)"""
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        logger.warning("BRAVE_API_KEY not set")
        return []

    try:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": api_key
        }
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers=headers,
            timeout=30
        )

        if response.ok:
            data = response.json()
            results = data.get("web", {}).get("results", [])
            logger.info(f"Brave Search direct API returned {len(results)} results")
            return results
        else:
            logger.error(f"Brave Search API error: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Brave Search direct call failed: {e}")
        return []


def search_news_via_mcp(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 20,
    server_name: str = "brave-search",
    tool_name: str = "brave_web_search",
) -> List[Dict[str, Any]]:
    """
    MCP 서버(예: brave-search)를 통해 뉴스/웹 검색을 수행합니다.

    MCP 서버와 툴 이름은 실제 서버 구현에 따라 다를 수 있으므로,
    필요시 server_name / tool_name을 조정해야 합니다.
    MCP 실패 시 직접 API 호출로 폴백합니다.
    """

    async def _call() -> Dict[str, Any]:
        return await call_mcp_tool(
            server_name,
            tool_name,
            {
                "query": query,
                "count": max_results,
            },
        )

    try:
        result = _run_coro(_call()) or {}
    except Exception as e:
        logger.warning(f"News MCP call failed: {e}, falling back to direct API")
        result = {}

    # 기사 리스트 후보 키들
    articles = (
        result.get("articles")
        or result.get("items")
        or result.get("results")
        or []
    )

    # MCP 실패 시 직접 Brave API 호출
    if not articles and server_name == "brave-search":
        articles = _fetch_brave_search_direct(query, max_results)

    out: List[Dict[str, Any]] = []
    for a in articles[:max_results]:
        out.append(
            {
                "title": a.get("title", ""),
                "description": a.get("description", "") or a.get("snippet", ""),
                "url": a.get("url", ""),
                "source": {"name": a.get("source") or a.get("site_name", "Brave Search")},
                "publishedAt": a.get("publishedAt") or a.get("published_at") or a.get("age"),
                "content": a.get("content", ""),
            }
        )

    return out
