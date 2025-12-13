"""
X (Twitter) API connector.

Supports:
- Recent search (Basic/Elevated access)
- Full-archive search (Academic/Enterprise access)
- Filtered stream (Real-time)
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

from .base import CollectedItem, SocialConnector

logger = logging.getLogger(__name__)


class XClient(SocialConnector):
    """X (Twitter) API v2 connector."""

    BASE_URL = "https://api.twitter.com/2"

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        super().__init__(timeout, max_retries)
        self._bearer_token = os.getenv("X_BEARER_TOKEN")
        self._academic_token = os.getenv("X_ACADEMIC_BEARER_TOKEN")
        self._enterprise_token = os.getenv("X_ENTERPRISE_BEARER_TOKEN")

    def is_configured(self) -> bool:
        """Check if X API credentials are configured."""
        return bool(self._bearer_token or self._academic_token or self._enterprise_token)

    def _get_headers(self, use_academic: bool = False) -> Dict[str, str]:
        """Get authorization headers."""
        token = self._academic_token if use_academic else self._bearer_token
        if not token:
            token = self._enterprise_token or self._bearer_token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def fetch_posts(
        self,
        query: str,
        max_results: int = 20,
        time_window: str = "24h",
        language: Optional[str] = None,
        exclude_retweets: bool = True,
        include_media: bool = False,
        **kwargs,
    ) -> List[CollectedItem]:
        """
        Fetch tweets matching the query.

        Args:
            query: Search query
            max_results: Maximum number of results (10-100 for basic, 10-500 for academic)
            time_window: Time window (e.g., "24h", "7d")
            language: Filter by language (e.g., "ko", "en")
            exclude_retweets: Exclude retweets from results
            include_media: Only include tweets with media

        Returns:
            List of CollectedItem objects
        """
        if not self.is_configured():
            logger.warning("X API not configured. Returning sample data.")
            return self._generate_sample_data("x", query, max_results)

        if not requests:
            logger.warning("requests library not available. Returning sample data.")
            return self._generate_sample_data("x", query, max_results)

        # Build query with filters
        full_query = self._build_query(query, language, exclude_retweets, include_media)

        # Calculate start time
        start_time = self._calculate_start_time(time_window)

        try:
            tweets = self._search_recent(
                full_query, max_results=min(max_results, 100), start_time=start_time
            )
            return tweets
        except Exception as e:
            logger.error(f"X API error: {e}")
            return self._generate_sample_data("x", query, max_results)

    def _build_query(
        self, query: str, language: Optional[str], exclude_retweets: bool, include_media: bool
    ) -> str:
        """Build Twitter search query with operators."""
        parts = [query]

        if language:
            parts.append(f"lang:{language}")

        if exclude_retweets:
            parts.append("-is:retweet")

        if include_media:
            parts.append("has:media")

        return " ".join(parts)

    def _calculate_start_time(self, time_window: str) -> str:
        """Calculate ISO 8601 start time from time window."""
        now = datetime.utcnow()

        if time_window.endswith("h"):
            hours = int(time_window[:-1])
            start = now - timedelta(hours=hours)
        elif time_window.endswith("d"):
            days = int(time_window[:-1])
            start = now - timedelta(days=days)
        elif time_window.endswith("w"):
            weeks = int(time_window[:-1])
            start = now - timedelta(weeks=weeks)
        else:
            # Default to 24 hours
            start = now - timedelta(hours=24)

        return start.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _search_recent(self, query: str, max_results: int, start_time: str) -> List[CollectedItem]:
        """Execute recent search API call."""
        url = f"{self.BASE_URL}/tweets/search/recent"

        params = {
            "query": query,
            "max_results": max_results,
            "start_time": start_time,
            "tweet.fields": "created_at,public_metrics,author_id,lang,entities",
            "expansions": "author_id",
            "user.fields": "username,name,public_metrics",
        }

        self._wait_for_rate_limit()

        response = requests.get(
            url, headers=self._get_headers(), params=params, timeout=self.timeout
        )

        # Update rate limit info
        if "x-rate-limit-remaining" in response.headers:
            self._update_rate_limit(
                int(response.headers["x-rate-limit-remaining"]),
                int(response.headers.get("x-rate-limit-reset", 0)),
            )

        response.raise_for_status()
        data = response.json()

        # Build user lookup
        users = {}
        for user in data.get("includes", {}).get("users", []):
            users[user["id"]] = user

        # Convert to CollectedItem
        items = []
        for tweet in data.get("data", []):
            author_id = tweet.get("author_id", "")
            author_info = users.get(author_id, {})

            metrics = tweet.get("public_metrics", {})
            entities = tweet.get("entities", {})

            # Extract hashtags and mentions
            hashtags = [tag["tag"] for tag in entities.get("hashtags", [])]
            mentions = [mention["username"] for mention in entities.get("mentions", [])]

            # Parse created_at
            created_at = tweet.get("created_at", "")
            published_at = self._parse_twitter_date(created_at)

            items.append(
                CollectedItem(
                    source="x",
                    title=tweet.get("text", "")[:80],
                    url=f"https://x.com/i/web/status/{tweet['id']}",
                    content=tweet.get("text", ""),
                    published_at=published_at,
                    language=tweet.get("lang", ""),
                    author=author_info.get("username", ""),
                    author_id=author_id,
                    views=metrics.get("impression_count", 0),
                    likes=metrics.get("like_count", 0),
                    comments=metrics.get("reply_count", 0),
                    shares=metrics.get("retweet_count", 0),
                    media_type="text",
                    hashtags=hashtags,
                    mentions=mentions,
                    raw_data=tweet,
                )
            )

        logger.info(f"Fetched {len(items)} tweets from X API")
        return items

    def _parse_twitter_date(self, date_str: str) -> Optional[float]:
        """Parse Twitter date format to timestamp."""
        if not date_str:
            return None

        try:
            # Twitter uses ISO 8601 format
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            return dt.timestamp()
        except ValueError:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
                return dt.timestamp()
            except ValueError:
                logger.warning(f"Failed to parse Twitter date: {date_str}")
                return None

    def fetch_user_timeline(self, user_id: str, max_results: int = 20) -> List[CollectedItem]:
        """
        Fetch tweets from a specific user's timeline.

        Args:
            user_id: Twitter user ID
            max_results: Maximum number of tweets

        Returns:
            List of CollectedItem objects
        """
        if not self.is_configured() or not requests:
            return []

        url = f"{self.BASE_URL}/users/{user_id}/tweets"

        params = {
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,lang,entities",
        }

        try:
            response = requests.get(
                url, headers=self._get_headers(), params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            items = []
            for tweet in data.get("data", []):
                items.append(
                    CollectedItem(
                        source="x",
                        title=tweet.get("text", "")[:80],
                        url=f"https://x.com/i/web/status/{tweet['id']}",
                        content=tweet.get("text", ""),
                        published_at=self._parse_twitter_date(tweet.get("created_at", "")),
                        author_id=user_id,
                        media_type="text",
                    )
                )

            return items

        except Exception as e:
            logger.error(f"Failed to fetch user timeline: {e}")
            return []

    def search_full_archive(
        self, query: str, start_time: str, end_time: str, max_results: int = 100
    ) -> List[CollectedItem]:
        """
        Search full archive (Academic/Enterprise access only).

        Args:
            query: Search query
            start_time: ISO 8601 start time
            end_time: ISO 8601 end time
            max_results: Maximum results per request (10-500)

        Returns:
            List of CollectedItem objects
        """
        if not self._academic_token and not self._enterprise_token:
            logger.warning("Full archive search requires Academic/Enterprise access")
            return []

        url = f"{self.BASE_URL}/tweets/search/all"

        params = {
            "query": query,
            "start_time": start_time,
            "end_time": end_time,
            "max_results": min(max_results, 500),
            "tweet.fields": "created_at,public_metrics,author_id,lang",
        }

        try:
            response = requests.get(
                url,
                headers=self._get_headers(use_academic=True),
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            items = []
            for tweet in data.get("data", []):
                items.append(
                    CollectedItem(
                        source="x",
                        title=tweet.get("text", "")[:80],
                        url=f"https://x.com/i/web/status/{tweet['id']}",
                        content=tweet.get("text", ""),
                        published_at=self._parse_twitter_date(tweet.get("created_at", "")),
                        language=tweet.get("lang", ""),
                        media_type="text",
                    )
                )

            return items

        except Exception as e:
            logger.error(f"Full archive search failed: {e}")
            return []
