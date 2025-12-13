"""
SNS 데이터 수집용 MCP 클라이언트 래퍼

- Supadata MCP 서버(기본: supadata-ai-mcp)를 통해서만
  X / TikTok / YouTube 데이터를 가져오도록 강제합니다.
- 개별 에이전트의 tools 모듈에서는 이 래퍼만 사용하고,
  직접 SNS HTTP API를 호출하지 않도록 합니다.

환경 변수:
- SUPADATA_MCP_SERVER   : 기본 MCP 서버 이름 (default: supadata-ai-mcp)
- SUPADATA_X_TOOL       : X 검색용 MCP 툴 이름   (default: x_search)
- SUPADATA_TIKTOK_TOOL  : TikTok 검색용 MCP 툴 이름 (default: tiktok_search)
- SUPADATA_YOUTUBE_TOOL : YouTube 트렌딩용 MCP 툴 이름 (default: youtube_trending)
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, Dict, List, Optional

from src.integrations.mcp.servers.mcp_client import call_mcp_tool
from src.integrations.mcp.supadata_contract import (
    parse_supadata_tiktok_videos,
    parse_supadata_x_posts,
    parse_supadata_youtube_videos,
)
from src.integrations.mcp.utils import retry_with_backoff

logger = logging.getLogger(__name__)


def _run_coro(coro):
    """동기 함수에서 async 함수를 호출하기 위한 헬퍼."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # 이미 이벤트 루프가 있을 경우 (예: Jupyter), 새 루프에서 실행
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@retry_with_backoff(retries=2, backoff_factor=1.5)
async def _call_mcp_safe(server: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """재시도 로직이 포함된 내부 호출 함수."""
    return await call_mcp_tool(server, tool, args)


async def fetch_x_posts_via_mcp_async(
    query: str,
    max_results: int = 20,
    server_name: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """X 포스트 수집 (Async)"""
    server = server_name or os.getenv("SUPADATA_MCP_SERVER", "supadata-ai-mcp")
    tool = tool_name or os.getenv("SUPADATA_X_TOOL", "x_search")

    try:
        result = await _call_mcp_safe(
            str(server),
            str(tool),
            {"query": query, "max_results": max_results},
        )
    except Exception as e:
        logger.error(f"X MCP call failed: {e}")
        return []

    _, posts = parse_supadata_x_posts(result or {})
    if not posts:
        logger.warning("Supadata X tool returned no parseable posts. Check SUPADATA_X_TOOL.")
        return []

    out: List[Dict[str, Any]] = []
    for p in posts[:max_results]:
        text = p.text or ""
        tweet_id = p.id or ""
        url = p.url or (f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "")
        out.append(
            {
                "source": "x",
                "title": text.split("\n")[0][:80],
                "url": url,
                "content": text,
                "created_at": p.created_at,
            }
        )
    return out


def fetch_x_posts_via_mcp(
    query: str,
    max_results: int = 20,
    server_name: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """X 포스트 수집 (Sync Wrapper)"""
    return _run_coro(fetch_x_posts_via_mcp_async(query, max_results, server_name, tool_name))


async def fetch_tiktok_videos_via_mcp_async(
    query: str,
    max_count: int = 20,
    server_name: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """TikTok 영상 수집 (Async)"""
    server = server_name or os.getenv("SUPADATA_MCP_SERVER", "supadata-ai-mcp")
    tool = tool_name or os.getenv("SUPADATA_TIKTOK_TOOL", "tiktok_search")

    try:
        result = await _call_mcp_safe(
            str(server),
            str(tool),
            {"query": query, "max_count": max_count},
        )
    except Exception as e:
        logger.error(f"TikTok MCP call failed: {e}")
        return []

    _, videos = parse_supadata_tiktok_videos(result or {})
    if not videos:
        logger.warning(
            "Supadata TikTok tool returned no parseable videos. Check SUPADATA_TIKTOK_TOOL."
        )
        return []

    out: List[Dict[str, Any]] = []
    for v in videos[:max_count]:
        out.append(
            {
                "video_id": v.id or "",
                "title": v.title or "",
                "channel": v.author or "",
                "views": int(v.views or 0),
                "likes": int(v.likes or 0),
                "comments": int(v.comments or 0),
                "published_at": v.published_at,
                "platform": "tiktok",
                "url": v.url or "",
                "thumbnail": v.thumbnail or "",
            }
        )
    return out


def fetch_tiktok_videos_via_mcp(
    query: str,
    max_count: int = 20,
    server_name: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """TikTok 영상 수집 (Sync Wrapper)"""
    return _run_coro(fetch_tiktok_videos_via_mcp_async(query, max_count, server_name, tool_name))


async def fetch_youtube_videos_via_mcp_async(
    market: str = "KR",
    time_window: str = "24h",
    max_results: int = 50,
    server_name: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """YouTube 트렌딩 수집 (Async)"""
    server = server_name or os.getenv("SUPADATA_MCP_SERVER", "supadata-ai-mcp")
    tool = tool_name or os.getenv("SUPADATA_YOUTUBE_TOOL", "youtube_trending")

    try:
        result = await _call_mcp_safe(
            str(server),
            str(tool),
            {
                "region": market,
                "time_window": time_window,
                "max_results": max_results,
            },
        )
    except Exception as e:
        logger.error(f"YouTube MCP call failed: {e}")
        return []

    _, videos = parse_supadata_youtube_videos(result or {})
    if not videos:
        logger.warning(
            "Supadata YouTube tool returned no parseable videos. Check SUPADATA_YOUTUBE_TOOL."
        )
        return []

    out: List[Dict[str, Any]] = []
    for v in videos[:max_results]:
        out.append(
            {
                "video_id": v.id or "",
                "title": v.title or "",
                "channel": v.channel or "",
                "views": int(v.views or 0),
                "likes": int(v.likes or 0),
                "comments": int(v.comments or 0),
                "published_at": v.published_at,
                "description": (v.description or "")[:200],
                "thumbnail": v.thumbnail or "",
                "platform": "youtube",
                "url": v.url or (f"https://www.youtube.com/watch?v={v.id}" if v.id else ""),
            }
        )
    return out


def fetch_youtube_videos_via_mcp(
    market: str = "KR",
    time_window: str = "24h",
    max_results: int = 50,
    server_name: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """YouTube 트렌딩 수집 (Sync Wrapper)"""
    return _run_coro(
        fetch_youtube_videos_via_mcp_async(market, time_window, max_results, server_name, tool_name)
    )


async def fetch_all_sns_trends_async(
    query: str,
    market: str = "KR",
    max_results: int = 20,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    모든 SNS 플랫폼(X, TikTok, YouTube) 데이터를 병렬로 수집합니다.
    """
    logger.info(f"Starting parallel SNS collection for query: {query}")

    # YouTube는 검색어가 아니라 market 트렌딩이므로 query 영향 없음 (필요시 검색 툴로 변경 가능)
    # 현재 스펙상 YouTube는 trending, 나머지는 keyword search

    results = await asyncio.gather(
        fetch_x_posts_via_mcp_async(query, max_results=max_results),
        fetch_tiktok_videos_via_mcp_async(query, max_count=max_results),
        fetch_youtube_videos_via_mcp_async(market=market, max_results=max_results),
        return_exceptions=True,
    )

    x_res, tiktok_res, youtube_res = results

    # 예외 처리
    final_results = {
        "x": x_res if isinstance(x_res, list) else [],
        "tiktok": tiktok_res if isinstance(tiktok_res, list) else [],
        "youtube": youtube_res if isinstance(youtube_res, list) else [],
    }

    total_count = sum(len(v) for v in final_results.values())
    logger.info(f"Parallel collection finished. Total items: {total_count}")
    return final_results


def fetch_all_sns_trends(
    query: str,
    market: str = "KR",
    max_results: int = 20,
) -> Dict[str, List[Dict[str, Any]]]:
    """모든 SNS 플랫폼 병렬 수집 (Sync Wrapper)"""
    return _run_coro(fetch_all_sns_trends_async(query, market, max_results))
