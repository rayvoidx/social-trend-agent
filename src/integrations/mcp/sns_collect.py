from __future__ import annotations

"""
SNS/비디오 데이터 수집용 MCP 클라이언트 래퍼

Supadata MCP 서버(@supadata/mcp)를 통해 비디오 트랜스크립트와 웹 콘텐츠를 수집합니다.

사용 가능한 Supadata MCP 도구:
- supadata_transcript: YouTube, TikTok, Instagram, Twitter 비디오 트랜스크립트 추출
- supadata_scrape: 웹 페이지 콘텐츠를 Markdown으로 추출
- supadata_map: 웹사이트의 모든 URL 수집
- supadata_crawl: 웹사이트 전체 크롤링
- supadata_check_transcript_status: 트랜스크립트 작업 상태 확인
- supadata_check_crawl_status: 크롤링 작업 상태 확인

환경 변수:
- SUPADATA_API_KEY: Supadata API 키 (필수)
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv(override=True)

from src.integrations.mcp.servers.mcp_client import call_mcp_tool

logger = logging.getLogger(__name__)

# MCP 서버 이름
SUPADATA_SERVER = "supadata-ai-mcp"


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


def fetch_video_transcript(
    url: str,
    lang: str = "ko",
    server_name: str = SUPADATA_SERVER,
) -> Dict[str, Any]:
    """
    비디오 URL에서 트랜스크립트를 추출합니다.

    지원 플랫폼: YouTube, TikTok, Instagram, Twitter

    Args:
        url: 비디오 URL
        lang: 트랜스크립트 언어 (기본: ko)
        server_name: MCP 서버 이름

    Returns:
        트랜스크립트 데이터 (content, lang, availableLangs 등)
    """
    async def _call() -> Dict[str, Any]:
        return await call_mcp_tool(
            server_name,
            "supadata_transcript",
            {"url": url, "lang": lang},
        )

    try:
        result = _run_coro(_call()) or {}
    except Exception as e:
        logger.error(f"Transcript extraction failed: {e}")
        return {"error": str(e)}

    return result


def fetch_youtube_transcript(
    video_id: str,
    lang: str = "ko",
) -> Dict[str, Any]:
    """
    YouTube 비디오 트랜스크립트를 추출합니다.

    Args:
        video_id: YouTube 비디오 ID
        lang: 트랜스크립트 언어

    Returns:
        트랜스크립트 데이터
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    return fetch_video_transcript(url, lang)


def fetch_tiktok_transcript(
    video_url: str,
    lang: str = "ko",
) -> Dict[str, Any]:
    """
    TikTok 비디오 트랜스크립트를 추출합니다.

    Args:
        video_url: TikTok 비디오 URL
        lang: 트랜스크립트 언어

    Returns:
        트랜스크립트 데이터
    """
    return fetch_video_transcript(video_url, lang)


def scrape_web_content(
    url: str,
    server_name: str = SUPADATA_SERVER,
) -> Dict[str, Any]:
    """
    웹 페이지 콘텐츠를 Markdown 형식으로 추출합니다.

    Args:
        url: 웹 페이지 URL
        server_name: MCP 서버 이름

    Returns:
        스크래핑된 콘텐츠 (markdown, title, metadata 등)
    """
    async def _call() -> Dict[str, Any]:
        return await call_mcp_tool(
            server_name,
            "supadata_scrape",
            {"url": url},
        )

    try:
        result = _run_coro(_call()) or {}
    except Exception as e:
        logger.error(f"Web scraping failed: {e}")
        return {"error": str(e)}

    return result


def map_website_urls(
    url: str,
    server_name: str = SUPADATA_SERVER,
) -> List[str]:
    """
    웹사이트의 모든 URL을 수집합니다.

    Args:
        url: 웹사이트 기본 URL
        server_name: MCP 서버 이름

    Returns:
        URL 목록
    """
    async def _call() -> Dict[str, Any]:
        return await call_mcp_tool(
            server_name,
            "supadata_map",
            {"url": url},
        )

    try:
        result = _run_coro(_call()) or {}
    except Exception as e:
        logger.error(f"Website mapping failed: {e}")
        return []

    return result.get("urls", [])


def create_crawl_job(
    url: str,
    server_name: str = SUPADATA_SERVER,
) -> Dict[str, Any]:
    """
    웹사이트 크롤링 작업을 생성합니다.

    Args:
        url: 크롤링할 웹사이트 URL
        server_name: MCP 서버 이름

    Returns:
        크롤링 작업 정보 (job_id 등)
    """
    async def _call() -> Dict[str, Any]:
        return await call_mcp_tool(
            server_name,
            "supadata_crawl",
            {"url": url},
        )

    try:
        result = _run_coro(_call()) or {}
    except Exception as e:
        logger.error(f"Crawl job creation failed: {e}")
        return {"error": str(e)}

    return result


def check_crawl_status(
    job_id: str,
    server_name: str = SUPADATA_SERVER,
) -> Dict[str, Any]:
    """
    크롤링 작업 상태를 확인합니다.

    Args:
        job_id: 크롤링 작업 ID
        server_name: MCP 서버 이름

    Returns:
        작업 상태 및 결과
    """
    async def _call() -> Dict[str, Any]:
        return await call_mcp_tool(
            server_name,
            "supadata_check_crawl_status",
            {"job_id": job_id},
        )

    try:
        result = _run_coro(_call()) or {}
    except Exception as e:
        logger.error(f"Crawl status check failed: {e}")
        return {"error": str(e)}

    return result


def extract_video_data_from_transcript(
    transcript_result: Dict[str, Any],
    platform: str = "youtube",
) -> List[Dict[str, Any]]:
    """
    트랜스크립트 결과에서 비디오 데이터를 추출하여 표준 형식으로 변환합니다.

    Args:
        transcript_result: fetch_video_transcript 결과
        platform: 플랫폼 이름

    Returns:
        표준화된 비디오 데이터 목록
    """
    if "error" in transcript_result:
        return []

    content = transcript_result.get("content", [])
    if not content:
        return []

    # 트랜스크립트 텍스트 결합
    full_text = " ".join([
        item.get("text", "")
        for item in content
        if isinstance(item, dict)
    ])

    return [{
        "platform": platform,
        "transcript": full_text,
        "lang": transcript_result.get("lang", ""),
        "available_langs": transcript_result.get("availableLangs", []),
        "segments": content,
    }]
