"""
트렌드 분석 MCP 서버

FastMCP를 사용하여 트렌드 분석 에이전트의 기능을 MCP 도구로 노출합니다.
Claude Desktop, VS Code 등 MCP 클라이언트에서 사용 가능합니다.

실행:
    uv run python -m src.integrations.mcp.trend_mcp_server
"""

from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, Optional, cast
import logging
import json

# SNS용 MCP 서버들 (직접 모듈에서 가져와 타입 체크 오류를 방지)
from src.integrations.mcp.servers.instagram_server import (  # type: ignore[import]
    InstagramMCPServer,
)
from src.integrations.mcp.servers.tiktok_server import (  # type: ignore[import]
    TikTokMCPServer,
)
from src.integrations.mcp.servers.x_server import (  # type: ignore[import]
    XMCPServer,
)

logger = logging.getLogger(__name__)

# MCP 서버 인스턴스 생성
mcp = FastMCP("trend-analysis-agent")


@mcp.tool()
async def analyze_news_trend(
    query: str,
    time_window: str = "7d",
    language: str = "ko"
) -> str:
    """
    뉴스 트렌드 분석을 실행합니다.

    Args:
        query: 분석할 키워드 또는 주제
        time_window: 분석 기간 (24h, 7d, 30d)
        language: 언어 (ko, en)

    Returns:
        분석 결과 JSON (감성 분석, 키워드, 요약 포함)
    """
    try:
        from src.agents.news_trend.graph import run_agent

        result = run_agent(
            query=query,
            time_window=time_window,
            language=language,
        )

        # Pydantic 모델을 dict로 변환
        if hasattr(result, "model_dump"):
            result_dict: Dict[str, Any] = cast(Dict[str, Any], result.model_dump())
        else:
            result_dict = cast(Dict[str, Any], result)

        return json.dumps({
            "status": "success",
            "query": query,
            "time_window": time_window,
            "language": language,
            "result": {
                "report_md": result_dict.get("report_md", ""),
                "analysis": result_dict.get("analysis", {}),
                "metrics": result_dict.get("metrics", {}),
                "run_id": result_dict.get("run_id", "")
            }
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"News trend analysis failed: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query": query
        }, ensure_ascii=False)


@mcp.tool()
async def analyze_viral_video(
    query: str,
    time_window: str = "7d",
    language: str = "ko"
) -> str:
    """
    바이럴 비디오 트렌드를 분석합니다.

    Args:
        query: 분석할 키워드 또는 주제
        time_window: 분석 기간 (24h, 7d, 30d)
        language: 언어 (ko, en)

    Returns:
        분석 결과 JSON (인기 영상, 성공 요소 포함)
    """
    try:
        from src.agents.viral_video.graph import run_agent

        result = run_agent(
            query=query,
            time_window=time_window,
        )

        if hasattr(result, "model_dump"):
            result_dict: Dict[str, Any] = cast(Dict[str, Any], result.model_dump())
        else:
            result_dict = cast(Dict[str, Any], result)

        return json.dumps({
            "status": "success",
            "query": query,
            "time_window": time_window,
            "result": {
                "report_md": result_dict.get("report_md", ""),
                "analysis": result_dict.get("analysis", {}),
                "metrics": result_dict.get("metrics", {}),
                "run_id": result_dict.get("run_id", "")
            }
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Viral video analysis failed: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query": query
        }, ensure_ascii=False)


@mcp.tool()
async def analyze_social_trend(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    platforms: Optional[str] = None
) -> str:
    """
    소셜 미디어 트렌드를 분석합니다.

    Args:
        query: 분석할 키워드 또는 주제
        time_window: 분석 기간 (24h, 7d, 30d)
        language: 언어 (ko, en)
        platforms: 분석할 플랫폼 (twitter, instagram, naver_blog - 콤마 구분)

    Returns:
        분석 결과 JSON (플랫폼별 트렌드, 감성 분석 포함)
    """
    try:
        from src.agents.social_trend.graph import run_agent

        platform_list = platforms.split(",") if platforms else None

        result = run_agent(
            query=query,
            sources=platform_list,
            time_window=time_window,
            language=language,
        )

        if hasattr(result, "model_dump"):
            result_dict: Dict[str, Any] = cast(Dict[str, Any], result.model_dump())
        else:
            result_dict = cast(Dict[str, Any], result)

        return json.dumps({
            "status": "success",
            "query": query,
            "time_window": time_window,
            "platforms": platform_list,
            "result": {
                "report_md": result_dict.get("report_md", ""),
                "analysis": result_dict.get("analysis", {}),
                "metrics": result_dict.get("metrics", {}),
                "run_id": result_dict.get("run_id", "")
            }
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Social trend analysis failed: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query": query
        }, ensure_ascii=False)


@mcp.tool()
async def x_search_tweets(
    query: str,
    max_results: int = 100,
    sort_order: str = "recency",
) -> str:
    """
    X(Twitter) MCP 서버를 통해 최근 트윗을 검색합니다.

    Args:
        query: 검색 쿼리 (키워드/해시태그 포함)
        max_results: 최대 트윗 수 (10~100)
        sort_order: 정렬 기준 (recency | relevancy)

    Returns:
        X MCP 서버에서 반환한 JSON 문자열
    """
    server = XMCPServer()
    try:
        result = await server.call_tool(
            "x_search_tweets",
            {
                "query": query,
                "max_results": max_results,
                "sort_order": sort_order,
            },
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"X MCP search failed: {e}", exc_info=True)
        return json.dumps(
            {"status": "error", "error": str(e), "query": query},
            ensure_ascii=False,
        )
    finally:
        await server.close()


@mcp.tool()
async def tiktok_search_videos(
    query: str,
    max_count: int = 20,
    sort_type: str = "relevance",
) -> str:
    """
    TikTok MCP 서버를 통해 영상 검색을 수행합니다.

    Args:
        query: 검색 키워드 또는 해시태그
        max_count: 최대 영상 개수
        sort_type: 정렬 기준 (relevance | like_count | create_date)

    Returns:
        TikTok MCP 서버에서 반환한 JSON 문자열
    """
    server = TikTokMCPServer()
    try:
        result = await server.call_tool(
            "tiktok_search_videos",
            {
                "query": query,
                "max_count": max_count,
                "sort_type": sort_type,
            },
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"TikTok MCP search failed: {e}", exc_info=True)
        return json.dumps(
            {"status": "error", "error": str(e), "query": query},
            ensure_ascii=False,
        )
    finally:
        await server.close()


@mcp.tool()
async def instagram_search_hashtag(
    hashtag: str,
    limit: int = 25,
) -> str:
    """
    Instagram MCP 서버를 통해 해시태그 기반 게시물을 조회합니다.

    Args:
        hashtag: 검색할 해시태그 (앞의 # 없이)
        limit: 최대 게시물 수

    Returns:
        Instagram MCP 서버에서 반환한 JSON 문자열
    """
    server = InstagramMCPServer()
    try:
        result = await server.call_tool(
            "instagram_search_hashtag",
            {
                "hashtag": hashtag,
                "limit": limit,
            },
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Instagram MCP hashtag search failed: {e}", exc_info=True)
        return json.dumps(
            {"status": "error", "error": str(e), "hashtag": hashtag},
            ensure_ascii=False,
        )
    finally:
        await server.close()


@mcp.tool()
async def get_task_status(task_id: str) -> str:
    """
    제출된 분석 태스크의 상태를 조회합니다.

    Args:
        task_id: 태스크 ID

    Returns:
        태스크 상태 JSON
    """
    # 분산 실행기에서 태스크 조회는 API 서버와 연동할 때 구현 예정
    return json.dumps({
        "task_id": task_id,
        "status": "pending",
        "message": "Task status check via MCP - connect to API server for full status"
    }, ensure_ascii=False)


@mcp.tool()
async def list_insights(
    source: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    저장된 인사이트 목록을 조회합니다.

    Args:
        source: 에이전트 소스 필터 (news_trend_agent, viral_video_agent, social_trend_agent)
        limit: 최대 결과 수

    Returns:
        인사이트 목록 JSON
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
            items.append({
                "id": i.id,
                "source": i.source.value,
                "query": i.query,
                "time_window": i.time_window,
                "language": i.language,
                "top_keywords": i.top_keywords[:5] if i.top_keywords else [],
                "created_at": i.created_at.isoformat()
            })

        return json.dumps({
            "total": len(items),
            "items": items
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool()
async def recommend_missions(insight_id: str) -> str:
    """
    인사이트를 기반으로 마케팅 미션과 크리에이터를 추천합니다.

    Args:
        insight_id: 인사이트 ID

    Returns:
        미션 및 크리에이터 추천 JSON
    """
    try:
        from src.domain.models import INSIGHT_REPOSITORY
        from src.domain.mission import generate_missions_from_insight, recommend_creators_for_mission

        insight = INSIGHT_REPOSITORY.get(insight_id)
        if not insight:
            return json.dumps({
                "status": "error",
                "error": f"Insight {insight_id} not found"
            }, ensure_ascii=False)

        missions = generate_missions_from_insight(insight)

        recommendations = []
        for m in missions:
            creators = recommend_creators_for_mission(m)
            recommendations.append({
                "mission": {
                    "id": m.id,
                    "title": m.title,
                    "description": m.description,
                    "platforms": [p.value for p in m.platforms],
                    "target_audience": m.target_audience
                },
                "creators": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "platform": c.primary_platform.value,
                        "followers": c.followers,
                        "engagement_rate": c.avg_engagement_rate
                    }
                    for c in creators
                ]
            })

        return json.dumps({
            "insight_id": insight_id,
            "count": len(recommendations),
            "recommendations": recommendations
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, ensure_ascii=False)


@mcp.tool()
async def web_search(query: str, top_k: int = 5) -> str:
    """
    웹 검색을 수행합니다.

    Args:
        query: 검색 쿼리
        top_k: 반환할 결과 수

    Returns:
        검색 결과 URL 목록 JSON
    """
    try:
        from src.mcp import WebSearchMCP

        search = WebSearchMCP()
        urls = search.search(query, top_k)

        return json.dumps({
            "query": query,
            "count": len(urls),
            "urls": urls
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "query": query
        }, ensure_ascii=False)


@mcp.tool()
async def fetch_url(url: str) -> str:
    """
    URL에서 콘텐츠를 가져옵니다.

    Args:
        url: 가져올 URL

    Returns:
        URL 콘텐츠 JSON (텍스트 또는 JSON)
    """
    try:
        from src.mcp import HttpMCP

        http = HttpMCP()
        result = http.fetch(url)

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e),
            "url": url
        }, ensure_ascii=False)


@mcp.resource("insights://list")
async def list_all_insights() -> str:
    """저장된 모든 인사이트 목록을 리소스로 제공합니다."""
    try:
        from src.domain.models import INSIGHT_REPOSITORY

        insights = list(INSIGHT_REPOSITORY.list())
        insights.sort(key=lambda i: i.created_at, reverse=True)

        items = []
        for i in insights[:50]:  # 최대 50개
            items.append({
                "id": i.id,
                "source": i.source.value,
                "query": i.query,
                "created_at": i.created_at.isoformat()
            })

        return json.dumps({"insights": items}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("config://agents")
async def get_agent_config() -> str:
    """에이전트 설정 정보를 리소스로 제공합니다."""
    return json.dumps({
        "agents": [
            {
                "name": "news_trend_agent",
                "description": "뉴스 트렌드 분석",
                "data_sources": ["NewsAPI", "Naver News"]
            },
            {
                "name": "viral_video_agent",
                "description": "바이럴 비디오 분석",
                "data_sources": ["YouTube"]
            },
            {
                "name": "social_trend_agent",
                "description": "소셜 미디어 트렌드 분석",
                "data_sources": ["Twitter/X", "Instagram", "Naver Blog"]
            }
        ],
        "version": "4.0.0"
    }, ensure_ascii=False, indent=2)


def main():
    """MCP 서버 실행"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting Trend Analysis MCP Server...")

    # stdio 전송으로 서버 실행
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
