"""
TikTok API connector.

Supports:
- TikTok for Business API
- Third-party connectors (Brandwatch, Talkwalker, etc.)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from .base import CollectedItem, SocialConnector

logger = logging.getLogger(__name__)


class TikTokClient(SocialConnector):
    """TikTok API connector."""

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        super().__init__(timeout, max_retries)

        # TikTok for Business API
        self._app_id = os.getenv("TIKTOK_APP_ID")
        self._app_secret = os.getenv("TIKTOK_APP_SECRET")
        self._access_token = os.getenv("TIKTOK_ACCESS_TOKEN")

        # Third-party connector
        self._connector_token = os.getenv("TIKTOK_CONNECTOR_TOKEN")
        self._connector_url = os.getenv("TIKTOK_API_URL")

        # Alternative providers
        self._brandwatch_key = os.getenv("BRANDWATCH_API_KEY")
        self._talkwalker_key = os.getenv("TALKWALKER_API_KEY")

    def is_configured(self) -> bool:
        """Check if TikTok API credentials are configured."""
        return bool(
            (self._access_token and self._app_id)
            or (self._connector_token and self._connector_url)
            or self._brandwatch_key
            or self._talkwalker_key
        )

    def fetch_posts(
        self, query: str, max_results: int = 20, market: str = "KR", **kwargs
    ) -> List[CollectedItem]:
        """
        Fetch TikTok posts/videos.

        Args:
            query: Search query or hashtag
            max_results: Maximum number of results
            market: Market/region code

        Returns:
            List of CollectedItem objects
        """
        if not self.is_configured():
            logger.warning("TikTok API not configured. Returning sample data.")
            return self._generate_sample_data("tiktok", query, max_results)

        if not requests:
            logger.warning("requests library not available. Returning sample data.")
            return self._generate_sample_data("tiktok", query, max_results)

        # Try different data sources in order of preference
        try:
            if self._access_token and self._app_id:
                return self._fetch_via_business_api(query, max_results, market)
            elif self._connector_token and self._connector_url:
                return self._fetch_via_connector(query, max_results, market)
            elif self._brandwatch_key:
                return self._fetch_via_brandwatch(query, max_results)
            elif self._talkwalker_key:
                return self._fetch_via_talkwalker(query, max_results)
            else:
                return self._generate_sample_data("tiktok", query, max_results)

        except Exception as e:
            logger.error(f"TikTok API error: {e}")
            return self._generate_sample_data("tiktok", query, max_results)

    def _fetch_via_business_api(
        self, query: str, max_results: int, market: str
    ) -> List[CollectedItem]:
        """Fetch data via TikTok for Business API."""
        # TikTok Business API endpoints
        url = "https://business-api.tiktok.com/open_api/v1.3/video/list/"

        headers = {
            "Access-Token": self._access_token,
            "Content-Type": "application/json",
        }

        params = {
            "business_id": self._app_id,
            "max_count": max_results,
        }

        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        items = []
        for video in data.get("data", {}).get("videos", []):
            items.append(self._convert_business_video(video))

        logger.info(f"Fetched {len(items)} videos from TikTok Business API")
        return items

    def _fetch_via_connector(
        self, query: str, max_results: int, market: str
    ) -> List[CollectedItem]:
        """Fetch data via third-party connector."""
        headers = {
            "Authorization": f"Bearer {self._connector_token}",
            "Content-Type": "application/json",
        }

        params = {
            "query": query,
            "region": market,
            "count": max_results,
            "type": "trending",
        }

        response = requests.get(
            self._connector_url, headers=headers, params=params, timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        items = []
        for video in data.get("videos", data.get("data", [])):
            items.append(self._convert_connector_video(video))

        logger.info(f"Fetched {len(items)} videos from TikTok connector")
        return items

    def _fetch_via_brandwatch(self, query: str, max_results: int) -> List[CollectedItem]:
        """Fetch data via Brandwatch API."""
        url = "https://api.brandwatch.com/projects/{project}/data/mentions"

        project_id = os.getenv("BRANDWATCH_PROJECT_ID")
        if not project_id:
            return []

        headers = {
            "Authorization": f"Bearer {self._brandwatch_key}",
        }

        params = {
            "queryId": query,
            "pageSize": max_results,
            "startDate": "now-7d",
            "endDate": "now",
        }

        response = requests.get(
            url.format(project=project_id), headers=headers, params=params, timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        items = []
        for mention in data.get("results", []):
            if mention.get("domain") == "tiktok.com":
                items.append(
                    CollectedItem(
                        source="tiktok",
                        title=mention.get("title", "")[:80],
                        url=mention.get("url", ""),
                        content=mention.get("fullText", ""),
                        published_at=self._parse_date(mention.get("date", "")),
                        author=mention.get("author", ""),
                        likes=mention.get("engagement", {}).get("likes", 0),
                        comments=mention.get("engagement", {}).get("comments", 0),
                        shares=mention.get("engagement", {}).get("shares", 0),
                    )
                )

        return items

    def _fetch_via_talkwalker(self, query: str, max_results: int) -> List[CollectedItem]:
        """Fetch data via Talkwalker API."""
        url = "https://api.talkwalker.com/api/v1/search/p/{project}/results"

        project_id = os.getenv("TALKWALKER_PROJECT_ID")
        if not project_id:
            return []

        headers = {
            "Authorization": f"Bearer {self._talkwalker_key}",
        }

        params = {
            "q": f"source:tiktok AND {query}",
            "limit": max_results,
        }

        response = requests.get(
            url.format(project=project_id), headers=headers, params=params, timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        items = []
        for result in data.get("result", {}).get("data", []):
            items.append(
                CollectedItem(
                    source="tiktok",
                    title=result.get("title", "")[:80],
                    url=result.get("url", ""),
                    content=result.get("content", ""),
                    published_at=self._parse_date(result.get("published", "")),
                    author=result.get("author_name", ""),
                    views=result.get("engagement", {}).get("views", 0),
                    likes=result.get("engagement", {}).get("likes", 0),
                    comments=result.get("engagement", {}).get("comments", 0),
                )
            )

        return items

    def _convert_business_video(self, video: Dict[str, Any]) -> CollectedItem:
        """Convert TikTok Business API video to CollectedItem."""
        return CollectedItem(
            source="tiktok",
            title=video.get("video_description", "")[:80],
            url=f"https://www.tiktok.com/@{video.get('display_name', '')}/video/{video.get('item_id', '')}",
            content=video.get("video_description", ""),
            published_at=video.get("create_time"),
            author=video.get("display_name", ""),
            author_id=video.get("creator_id", ""),
            views=video.get("video_views", 0),
            likes=video.get("likes", 0),
            comments=video.get("comments", 0),
            shares=video.get("shares", 0),
            media_type="video",
            thumbnail_url=video.get("thumbnail_url", ""),
            raw_data=video,
        )

    def _convert_connector_video(self, video: Dict[str, Any]) -> CollectedItem:
        """Convert third-party connector video to CollectedItem."""
        stats = video.get("stats", video.get("statistics", {}))
        author = video.get("author", {})

        return CollectedItem(
            source="tiktok",
            title=video.get("desc", video.get("description", ""))[:80],
            url=video.get("webVideoUrl", video.get("url", "")),
            content=video.get("desc", video.get("description", "")),
            published_at=video.get("createTime", video.get("created_at")),
            author=author.get("nickname", author.get("username", "")),
            author_id=author.get("id", ""),
            views=stats.get("playCount", stats.get("views", 0)),
            likes=stats.get("diggCount", stats.get("likes", 0)),
            comments=stats.get("commentCount", stats.get("comments", 0)),
            shares=stats.get("shareCount", stats.get("shares", 0)),
            media_type="video",
            hashtags=[
                tag.get("hashtagName", tag.get("name", ""))
                for tag in video.get("challenges", video.get("hashtags", []))
            ],
            raw_data=video,
        )

    def _parse_date(self, date_str: str) -> Optional[float]:
        """Parse date string to timestamp."""
        if not date_str:
            return None

        # Try different formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.timestamp()
            except ValueError:
                continue

        # If it's already a timestamp
        try:
            return float(date_str)
        except (ValueError, TypeError):
            return None

    def fetch_trending(self, market: str = "KR", max_results: int = 50) -> List[CollectedItem]:
        """
        Fetch trending videos for a market.

        Args:
            market: Market/region code
            max_results: Maximum number of results

        Returns:
            List of CollectedItem objects
        """
        return self.fetch_posts(query="trending", max_results=max_results, market=market)

    def fetch_hashtag_videos(
        self, hashtag: str, max_results: int = 20, market: str = "KR"
    ) -> List[CollectedItem]:
        """
        Fetch videos for a specific hashtag.

        Args:
            hashtag: Hashtag name (without #)
            max_results: Maximum number of results
            market: Market/region code

        Returns:
            List of CollectedItem objects
        """
        return self.fetch_posts(query=f"#{hashtag}", max_results=max_results, market=market)
