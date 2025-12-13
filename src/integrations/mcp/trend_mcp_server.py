"""
Trend Analysis MCP Server (FastMCP).

Exposes agent capabilities and Supadata MCP collection helpers as MCP tools.

Run:
  uv run python -m src.integrations.mcp.trend_mcp_server
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, cast

from mcp.server.fastmcp import FastMCP

from src.integrations.mcp.sns_collect import (
    fetch_x_posts_via_mcp_async,
    fetch_tiktok_videos_via_mcp_async,
    fetch_youtube_trending_via_mcp_async,
)

logger = logging.getLogger(__name__)

mcp = FastMCP("trend-analysis-agent")


def _dump(result: Any) -> Dict[str, Any]:
    if hasattr(result, "model_dump"):
        return cast(Dict[str, Any], result.model_dump())
    if isinstance(result, dict):
        return cast(Dict[str, Any], result)
    return {"result": result}


@mcp.tool()
async def analyze_news_trend(query: str, time_window: str = "7d", language: str = "ko") -> str:
    """Run news_trend_agent and return JSON string."""
    try:
        from src.agents.news_trend.graph import run_agent

        result = run_agent(query=query, time_window=time_window, language=language, require_approval=False)
        d = _dump(result)
        return json.dumps(
            {
                "status": "success",
                "agent": "news_trend_agent",
                "query": query,
                "time_window": time_window,
                "language": language,
                "result": d,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        logger.error("News trend analysis failed", exc_info=True)
        return json.dumps({"status": "error", "error": str(e), "query": query}, ensure_ascii=False)


@mcp.tool()
async def analyze_viral_video(query: str, time_window: str = "24h", market: str = "KR") -> str:
    """Run viral_video_agent and return JSON string."""
    try:
        from src.agents.viral_video.graph import run_agent

        result = run_agent(query=query, time_window=time_window, market=market, require_approval=False)
        d = _dump(result)
        return json.dumps(
            {
                "status": "success",
                "agent": "viral_video_agent",
                "query": query,
                "time_window": time_window,
                "market": market,
                "result": d,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        logger.error("Viral video analysis failed", exc_info=True)
        return json.dumps({"status": "error", "error": str(e), "query": query}, ensure_ascii=False)


@mcp.tool()
async def analyze_social_trend(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    platforms: Optional[str] = None,
    max_results: int = 50,
) -> str:
    """Run social_trend_agent and return JSON string."""
    try:
        from src.agents.social_trend.graph import run_agent

        source_list: Optional[List[str]] = None
        if platforms:
            source_list = [p.strip() for p in platforms.split(",") if p.strip()]

        result = run_agent(
            query=query,
            time_window=time_window,
            language=language,
            sources=source_list,
            max_results=max_results,
            require_approval=False,
        )
        d = _dump(result)
        return json.dumps(
            {
                "status": "success",
                "agent": "social_trend_agent",
                "query": query,
                "time_window": time_window,
                "language": language,
                "platforms": source_list or [],
                "result": d,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        logger.error("Social trend analysis failed", exc_info=True)
        return json.dumps({"status": "error", "error": str(e), "query": query}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Supadata MCP collection helpers (SNS collection tools)
# ---------------------------------------------------------------------------


@mcp.tool()
async def x_search(query: str, max_results: int = 20) -> str:
    """Fetch X posts via Supadata MCP and return JSON string."""
    posts = await fetch_x_posts_via_mcp_async(query=query, max_results=max_results)
    return json.dumps({"status": "success", "query": query, "posts": posts}, ensure_ascii=False, indent=2)


@mcp.tool()
async def tiktok_search(query: str, max_count: int = 20) -> str:
    """Fetch TikTok videos via Supadata MCP and return JSON string."""
    videos = await fetch_tiktok_videos_via_mcp_async(query=query, max_count=max_count)
    return json.dumps({"status": "success", "query": query, "videos": videos}, ensure_ascii=False, indent=2)


@mcp.tool()
async def youtube_trending(market: str = "KR", limit: int = 20) -> str:
    """Fetch YouTube trending via Supadata MCP and return JSON string."""
    videos = await fetch_youtube_trending_via_mcp_async(market=market, limit=limit)
    return json.dumps({"status": "success", "market": market, "videos": videos}, ensure_ascii=False, indent=2)


def main() -> None:
    # Default MCP transport is stdio for desktop clients
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


