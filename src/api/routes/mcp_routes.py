"""
MCP 도구 API 라우트

MCP 서버의 도구들을 REST API로 노출합니다.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Any
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["MCP Tools"])


# ============================================================================
# 요청/응답 모델
# ============================================================================


class WebSearchRequest(BaseModel):
    """웹 검색 요청"""

    query: str = Field(..., description="검색 쿼리")
    top_k: int = Field(default=5, ge=1, le=20, description="반환할 결과 수")


class FetchUrlRequest(BaseModel):
    """URL 가져오기 요청"""

    url: str = Field(..., description="가져올 URL")


class InsightListRequest(BaseModel):
    """인사이트 목록 요청"""

    source: Optional[str] = Field(default=None, description="소스 필터")
    limit: int = Field(default=10, ge=1, le=100)


class MissionRecommendRequest(BaseModel):
    """미션 추천 요청"""

    insight_id: str = Field(..., description="인사이트 ID")


class YouTubeSearchRequest(BaseModel):
    """YouTube 검색 요청"""

    query: str = Field(..., description="검색 쿼리")
    max_results: int = Field(default=10, ge=1, le=50)
    channel_id: Optional[str] = Field(default=None, description="특정 채널 ID")


class YouTubeChannelRequest(BaseModel):
    """YouTube 채널 영상 요청"""

    channel_id: Optional[str] = Field(default=None, description="채널 ID")
    channel_handle: Optional[str] = Field(default=None, description="채널 핸들 (@handle)")
    max_results: int = Field(default=10, ge=1, le=50)


# ============================================================================
# MCP 도구 엔드포인트
# ============================================================================


@router.post("/web-search")
async def web_search(request: WebSearchRequest):
    """
    웹 검색 수행

    Brave Search 또는 SerpAPI를 사용하여 웹 검색을 수행합니다.
    """
    try:
        from src.mcp import WebSearchMCP

        search = WebSearchMCP()
        urls = search.search(request.query, request.top_k)

        return {"query": request.query, "count": len(urls), "urls": urls}
    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-url")
async def fetch_url(request: FetchUrlRequest):
    """
    URL에서 콘텐츠 가져오기

    지정된 URL에서 텍스트 또는 JSON 콘텐츠를 가져옵니다.
    """
    try:
        from src.mcp import HttpMCP

        http = HttpMCP()
        result = http.fetch(request.url)

        return result
    except Exception as e:
        logger.error(f"URL fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights")
async def list_insights(source: Optional[str] = None, limit: int = 10):
    """
    저장된 인사이트 목록 조회
    """
    try:
        from src.domain.models import INSIGHT_REPOSITORY, InsightSource

        insights = list(INSIGHT_REPOSITORY.list())

        # 소스 필터링
        if source:
            try:
                src_enum = InsightSource(source)
                insights = [i for i in insights if i.source == src_enum]
            except ValueError:
                pass

        # 정렬 및 제한
        insights.sort(key=lambda i: i.created_at, reverse=True)
        insights = insights[:limit]

        items = []
        for i in insights:
            items.append(
                {
                    "id": i.id,
                    "source": i.source.value,
                    "query": i.query,
                    "time_window": i.time_window,
                    "language": i.language,
                    "sentiment_summary": i.sentiment_summary,
                    "top_keywords": i.top_keywords[:5] if i.top_keywords else [],
                    "created_at": i.created_at.isoformat(),
                }
            )

        return {"total": len(items), "items": items}
    except Exception as e:
        logger.error(f"List insights failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend-missions")
async def recommend_missions(request: MissionRecommendRequest):
    """
    인사이트 기반 미션 및 크리에이터 추천
    """
    try:
        from src.domain.models import INSIGHT_REPOSITORY
        from src.domain.mission import (
            generate_missions_from_insight,
            recommend_creators_for_mission,
        )

        insight = INSIGHT_REPOSITORY.get(request.insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail=f"Insight {request.insight_id} not found")

        missions = generate_missions_from_insight(insight)

        recommendations = []
        for m in missions:
            creators = recommend_creators_for_mission(m)
            recommendations.append(
                {
                    "mission": {
                        "id": m.id,
                        "title": m.title,
                        "description": m.description,
                        "platforms": [p.value for p in m.platforms],
                        "target_audience": m.target_audience,
                        "expected_start": (
                            m.expected_start.isoformat() if m.expected_start else None
                        ),
                        "expected_end": m.expected_end.isoformat() if m.expected_end else None,
                    },
                    "creators": [
                        {
                            "id": c.id,
                            "name": c.name,
                            "handle": c.handle,
                            "platform": c.primary_platform.value,
                            "followers": c.followers,
                            "avg_view_per_post": c.avg_view_per_post,
                            "engagement_rate": c.avg_engagement_rate,
                        }
                        for c in creators
                    ],
                }
            )

        return {
            "insight_id": request.insight_id,
            "count": len(recommendations),
            "recommendations": recommendations,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mission recommendation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/youtube/search")
async def youtube_search(request: YouTubeSearchRequest):
    """
    YouTube 영상 검색
    """
    try:
        from src.mcp import YouTubeMCP

        youtube = YouTubeMCP()
        if not youtube.youtube:
            raise HTTPException(status_code=503, detail="YouTube API not configured")

        videos = youtube.search_videos(
            query=request.query, max_results=request.max_results, channel_id=request.channel_id
        )

        return {"query": request.query, "count": len(videos), "videos": videos}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YouTube search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/youtube/channel-videos")
async def youtube_channel_videos(request: YouTubeChannelRequest):
    """
    YouTube 채널 영상 목록
    """
    try:
        from src.mcp import YouTubeMCP

        youtube = YouTubeMCP()
        if not youtube.youtube:
            raise HTTPException(status_code=503, detail="YouTube API not configured")

        videos = youtube.get_channel_videos(
            channel_id=request.channel_id,
            channel_username=request.channel_handle,
            max_results=request.max_results,
        )

        return {
            "channel_id": request.channel_id,
            "channel_handle": request.channel_handle,
            "count": len(videos),
            "videos": videos,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YouTube channel videos failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def list_tools():
    """
    사용 가능한 MCP 도구 목록
    """
    return {
        "tools": [
            {
                "name": "web_search",
                "endpoint": "/api/mcp/web-search",
                "method": "POST",
                "description": "Brave/SerpAPI를 사용한 웹 검색",
            },
            {
                "name": "fetch_url",
                "endpoint": "/api/mcp/fetch-url",
                "method": "POST",
                "description": "URL에서 콘텐츠 가져오기",
            },
            {
                "name": "list_insights",
                "endpoint": "/api/mcp/insights",
                "method": "GET",
                "description": "저장된 인사이트 목록",
            },
            {
                "name": "recommend_missions",
                "endpoint": "/api/mcp/recommend-missions",
                "method": "POST",
                "description": "미션 및 크리에이터 추천",
            },
            {
                "name": "youtube_search",
                "endpoint": "/api/mcp/youtube/search",
                "method": "POST",
                "description": "YouTube 영상 검색",
            },
            {
                "name": "youtube_channel_videos",
                "endpoint": "/api/mcp/youtube/channel-videos",
                "method": "POST",
                "description": "YouTube 채널 영상 목록",
            },
        ]
    }
