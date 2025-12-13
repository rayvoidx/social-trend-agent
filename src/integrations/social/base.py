"""
Base classes for social media connectors.
"""

from __future__ import annotations

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CollectedItem:
    """Normalized data structure for collected social media items."""

    source: str
    title: str
    url: str
    content: str
    published_at: Optional[float] = None
    language: Optional[str] = None
    author: Optional[str] = None
    author_id: Optional[str] = None

    # Engagement metrics
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0

    # Additional metadata
    media_type: Optional[str] = None  # text, image, video
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    thumbnail_url: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

    @property
    def content_hash(self) -> str:
        """Generate hash for deduplication."""
        content_str = f"{self.url}:{self.content[:200]}"
        return hashlib.sha256(content_str.encode()).hexdigest()

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate."""
        if self.views == 0:
            return 0.0
        return (self.likes + self.comments + self.shares) / self.views

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "published_at": self.published_at,
            "language": self.language,
            "author": self.author,
            "author_id": self.author_id,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "media_type": self.media_type,
            "hashtags": self.hashtags,
            "mentions": self.mentions,
            "thumbnail_url": self.thumbnail_url,
            "content_hash": self.content_hash,
            "engagement_rate": self.engagement_rate,
        }


class SocialConnector(ABC):
    """Base class for social media API connectors."""

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[float] = None

    @abstractmethod
    def fetch_posts(self, query: str, max_results: int = 20, **kwargs) -> List[CollectedItem]:
        """
        Fetch posts matching the query.

        Args:
            query: Search query or hashtag
            max_results: Maximum number of results to return
            **kwargs: Additional platform-specific parameters

        Returns:
            List of CollectedItem objects
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the connector is properly configured with API credentials."""
        pass

    def _wait_for_rate_limit(self):
        """Wait if rate limited."""
        if self._rate_limit_reset and time.time() < self._rate_limit_reset:
            if self._rate_limit_remaining is not None and self._rate_limit_remaining <= 0:
                wait_time = self._rate_limit_reset - time.time()
                if wait_time > 0:
                    logger.warning(f"Rate limited. Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)

    def _update_rate_limit(self, remaining: int, reset_time: float):
        """Update rate limit info from API response."""
        self._rate_limit_remaining = remaining
        self._rate_limit_reset = reset_time

    def _generate_sample_data(self, source: str, query: str, count: int) -> List[CollectedItem]:
        """Generate sample data when API is not available."""
        items = []
        for i in range(count):
            items.append(
                CollectedItem(
                    source=source,
                    title=f"{query} sample {i+1}",
                    url=f"https://example.com/{source}/{i+1}",
                    content=f"This is sample content about {query} from {source}. "
                    f"Sample number {i+1}.",
                    published_at=time.time() - (i * 3600),
                    language="en",
                    author=f"sample_user_{i % 5}",
                    views=1000 + i * 100,
                    likes=50 + i * 10,
                    comments=5 + i,
                    media_type="text",
                    hashtags=[query.replace(" ", "").lower()],
                )
            )
        return items


def deduplicate_items(items: List[CollectedItem]) -> List[CollectedItem]:
    """Remove duplicate items based on content hash."""
    seen_hashes = set()
    unique_items = []

    for item in items:
        if item.content_hash not in seen_hashes:
            seen_hashes.add(item.content_hash)
            unique_items.append(item)

    logger.info(f"Deduplicated {len(items)} items to {len(unique_items)}")
    return unique_items


def filter_by_time_window(
    items: List[CollectedItem], start_time: float, end_time: Optional[float] = None
) -> List[CollectedItem]:
    """Filter items by time window."""
    if end_time is None:
        end_time = time.time()

    filtered = [
        item for item in items if item.published_at and start_time <= item.published_at <= end_time
    ]

    logger.info(f"Filtered {len(items)} items to {len(filtered)} by time window")
    return filtered
