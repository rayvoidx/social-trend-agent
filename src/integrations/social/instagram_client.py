"""
Instagram (Meta Graph API) connector.

Supports:
- Hashtag search
- User media feed
- Business account insights
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from .base import CollectedItem, SocialConnector

logger = logging.getLogger(__name__)


class InstagramClient(SocialConnector):
    """Instagram Graph API connector."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        super().__init__(timeout, max_retries)
        self._access_token = os.getenv("META_ACCESS_TOKEN")
        self._app_id = os.getenv("META_APP_ID")
        self._app_secret = os.getenv("META_APP_SECRET")
        self._business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

    def is_configured(self) -> bool:
        """Check if Instagram API credentials are configured."""
        return bool(self._access_token and self._business_account_id)

    def fetch_posts(
        self,
        query: str,
        max_results: int = 20,
        **kwargs
    ) -> List[CollectedItem]:
        """
        Fetch Instagram posts by hashtag.

        Args:
            query: Hashtag to search (without #)
            max_results: Maximum number of results

        Returns:
            List of CollectedItem objects
        """
        if not self.is_configured():
            logger.warning("Instagram API not configured. Returning sample data.")
            return self._generate_sample_data("instagram", query, max_results)

        if not requests:
            logger.warning("requests library not available. Returning sample data.")
            return self._generate_sample_data("instagram", query, max_results)

        try:
            # Search for hashtag ID first
            hashtag_id = self._get_hashtag_id(query.lstrip("#"))
            if not hashtag_id:
                logger.warning(f"Hashtag '{query}' not found")
                return self._generate_sample_data("instagram", query, max_results)

            # Get recent media for hashtag
            items = self._get_hashtag_recent_media(hashtag_id, max_results)
            return items

        except Exception as e:
            logger.error(f"Instagram API error: {e}")
            return self._generate_sample_data("instagram", query, max_results)

    def _get_hashtag_id(self, hashtag: str) -> Optional[str]:
        """Get hashtag ID from hashtag name."""
        url = f"{self.BASE_URL}/ig_hashtag_search"

        params = {
            "user_id": self._business_account_id,
            "q": hashtag,
            "access_token": self._access_token,
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        hashtags = data.get("data", [])
        if hashtags:
            return hashtags[0].get("id")

        return None

    def _get_hashtag_recent_media(
        self,
        hashtag_id: str,
        max_results: int
    ) -> List[CollectedItem]:
        """Get recent media for a hashtag."""
        url = f"{self.BASE_URL}/{hashtag_id}/recent_media"

        params = {
            "user_id": self._business_account_id,
            "fields": "id,caption,media_type,media_url,permalink,timestamp,"
                      "like_count,comments_count,username",
            "access_token": self._access_token,
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        items = []
        for media in data.get("data", [])[:max_results]:
            caption = media.get("caption", "")

            # Extract hashtags from caption
            hashtags = [
                word[1:] for word in caption.split()
                if word.startswith("#")
            ]

            # Parse timestamp
            timestamp = media.get("timestamp", "")
            published_at = self._parse_instagram_date(timestamp)

            items.append(
                CollectedItem(
                    source="instagram",
                    title=caption[:80] if caption else "Instagram Post",
                    url=media.get("permalink", ""),
                    content=caption,
                    published_at=published_at,
                    author=media.get("username", ""),
                    likes=media.get("like_count", 0),
                    comments=media.get("comments_count", 0),
                    media_type=media.get("media_type", "").lower(),
                    hashtags=hashtags,
                    thumbnail_url=media.get("media_url", ""),
                    raw_data=media,
                )
            )

        logger.info(f"Fetched {len(items)} posts from Instagram API")
        return items

    def _parse_instagram_date(self, date_str: str) -> Optional[float]:
        """Parse Instagram timestamp to Unix timestamp."""
        if not date_str:
            return None

        try:
            # Instagram uses ISO 8601 format
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
            return dt.timestamp()
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                return dt.timestamp()
            except ValueError:
                logger.warning(f"Failed to parse Instagram date: {date_str}")
                return None

    def fetch_user_media(
        self,
        user_id: Optional[str] = None,
        max_results: int = 20
    ) -> List[CollectedItem]:
        """
        Fetch media from business account.

        Args:
            user_id: Instagram user ID (defaults to configured business account)
            max_results: Maximum number of results

        Returns:
            List of CollectedItem objects
        """
        if not self.is_configured() or not requests:
            return []

        account_id = user_id or self._business_account_id
        url = f"{self.BASE_URL}/{account_id}/media"

        params = {
            "fields": "id,caption,media_type,media_url,permalink,timestamp,"
                      "like_count,comments_count,insights.metric(engagement,impressions,reach)",
            "access_token": self._access_token,
            "limit": max_results,
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            items = []
            for media in data.get("data", []):
                caption = media.get("caption", "")

                # Get insights if available
                insights = {}
                for insight in media.get("insights", {}).get("data", []):
                    insights[insight["name"]] = insight["values"][0]["value"]

                items.append(
                    CollectedItem(
                        source="instagram",
                        title=caption[:80] if caption else "Instagram Post",
                        url=media.get("permalink", ""),
                        content=caption,
                        published_at=self._parse_instagram_date(
                            media.get("timestamp", "")
                        ),
                        views=insights.get("impressions", 0),
                        likes=media.get("like_count", 0),
                        comments=media.get("comments_count", 0),
                        media_type=media.get("media_type", "").lower(),
                        thumbnail_url=media.get("media_url", ""),
                        raw_data=media,
                    )
                )

            return items

        except Exception as e:
            logger.error(f"Failed to fetch user media: {e}")
            return []

    def get_account_insights(
        self,
        metric: str = "impressions",
        period: str = "day",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get account-level insights.

        Args:
            metric: Metric to retrieve (impressions, reach, follower_count, etc.)
            period: Period (day, week, days_28)
            user_id: Instagram user ID

        Returns:
            Insights data
        """
        if not self.is_configured() or not requests:
            return {}

        account_id = user_id or self._business_account_id
        url = f"{self.BASE_URL}/{account_id}/insights"

        params = {
            "metric": metric,
            "period": period,
            "access_token": self._access_token,
        }

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get account insights: {e}")
            return {}
