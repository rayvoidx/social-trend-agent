from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.integrations.mcp.sns_collect import fetch_x_posts_via_mcp
from src.integrations.mcp.news_collect import search_news_via_mcp


@dataclass
class CollectedItem:
    source: str
    title: str
    url: str
    content: str
    published_at: Optional[float] = None


def _safe_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    (호환성을 위해 남겨둔) HTTP GET 래퍼.

    현재 SNS 수집은 MCP 서버를 통해서만 이루어지므로,
    이 함수는 RSS 등 다른 용도에서만 사용됩니다.
    """
    try:
        import requests  # type: ignore
    except ImportError:
        return None

    try:
        r = requests.get(url, headers=headers or {}, params=params or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()  # type: ignore
    except Exception:
        return None


def fetch_x_posts(query: str, max_results: int = 20) -> List[CollectedItem]:
    """
    X(구 Twitter)에서 최신 포스트를 가져옵니다.

    Args:
        query: 검색 쿼리
        max_results: 최대 결과 수 (기본값: 20)

    Returns:
        수집된 포스트 목록
    """
    # MCP 서버를 통해서만 X 데이터를 가져옵니다.
    raw = fetch_x_posts_via_mcp(query=query, max_results=max_results)
    items: List[CollectedItem] = []
    for t in raw:
        items.append(
            CollectedItem(
                source="x",
                title=t.get("title", ""),
                url=t.get("url", ""),
                content=t.get("content", ""),
                published_at=_ts(t.get("created_at")),
            )
        )
    # MCP 결과가 비어 있는 경우에도 더 이상 직접 API를 호출하지 않고 빈 리스트/샘플 데이터만 사용
    if not items:
        return _sample_items("x", query, max_results)
    return items


def fetch_instagram_posts(query: str, max_results: int = 20) -> List[CollectedItem]:
    """
    Instagram에서 포스트를 가져옵니다.

    Note: Instagram API는 공식 비즈니스 계정이 필요합니다.
    현재는 샘플 데이터를 반환합니다.

    Args:
        query: 검색 쿼리
        max_results: 최대 결과 수

    Returns:
        수집된 포스트 목록 (현재는 샘플 데이터)
    """
    # Public IG APIs are restricted; keep as stub unless user provides connector
    return _sample_items("instagram", query, max_results)


def fetch_naver_blog_posts(query: str, max_results: int = 20) -> List[CollectedItem]:
    """
    네이버 블로그에서 포스트를 가져옵니다.

    Args:
        query: 검색 쿼리
        max_results: 최대 결과 수 (기본값: 20)

    Returns:
        수집된 블로그 포스트 목록
    """
    # Naver Blog도 MCP 기반 웹/뉴스 검색으로만 수집
    results = search_news_via_mcp(
        query=f"site:blog.naver.com {query}",
        time_window="7d",
        language="ko",
        max_results=max_results,
    )
    items: List[CollectedItem] = []
    for r in results[:max_results]:
        items.append(
            CollectedItem(
                source="naver_blog",
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("description", "") or r.get("content", ""),
                published_at=None,
            )
        )
    if not items:
        return _sample_items("naver_blog", query, max_results)
    return items


def fetch_rss_feeds(feed_urls: List[str], max_results: int = 20) -> List[CollectedItem]:
    try:
        import feedparser  # type: ignore
    except Exception:
        # Fallback without feedparser
        return []

    collected: List[CollectedItem] = []
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
            for e in parsed.get("entries", [])[:max_results - len(collected)]:
                collected.append(
                    CollectedItem(
                        source="rss",
                        title=e.get("title", "")[:120],
                        url=e.get("link", ""),
                        content=e.get("summary", ""),
                        published_at=_ts(e.get("published")),
                    )
                )
                if len(collected) >= max_results:
                    break
        except Exception:
            continue
        if len(collected) >= max_results:
            break
    return collected


def normalize_items(items: List[CollectedItem]) -> List[Dict[str, Any]]:
    """
    수집된 아이템을 정규화된 딕셔너리 형태로 변환합니다.

    Args:
        items: 수집된 아이템 목록

    Returns:
        정규화된 딕셔너리 목록
    """
    normalized: List[Dict[str, Any]] = []
    for it in items:
        # Handle both dict and object types
        if isinstance(it, dict):
            normalized.append(
                {
                    "source": it.get("source", ""),
                    "title": it.get("title", ""),
                    "url": it.get("url", ""),
                    "content": it.get("content", ""),
                    "published_at": it.get("published_at", ""),
                }
            )
        else:
            normalized.append(
                {
                    "source": it.source,
                    "title": it.title,
                    "url": it.url,
                    "content": it.content,
                    "published_at": it.published_at,
                }
            )
    return normalized


def analyze_sentiment_and_keywords(texts: List[str]) -> Dict[str, Any]:
    """
    텍스트 목록에서 감성과 키워드를 분석합니다.

    Args:
        texts: 분석할 텍스트 목록

    Returns:
        감성 분석 결과 및 키워드 목록을 포함한 딕셔너리
    """
    positive_tokens = ["great", "good", "love", "추천", "만족", "좋"]
    negative_tokens = ["bad", "hate", "불만", "나쁨", "싫", "문제"]

    pos = neg = neu = 0
    freq: Dict[str, int] = {}
    for t in texts:
        lt = (t or "").lower()
        score = 0
        for tok in positive_tokens:
            if tok in lt:
                score += 1
                freq[tok] = freq.get(tok, 0) + 1
        for tok in negative_tokens:
            if tok in lt:
                score -= 1
                freq[tok] = freq.get(tok, 0) + 1
        if score > 0:
            pos += 1
        elif score < 0:
            neg += 1
        else:
            neu += 1

    total = max(1, pos + neg + neu)
    top_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "sentiment": {
            "positive": pos,
            "neutral": neu,
            "negative": neg,
            "positive_pct": (pos / total) * 100.0,
            "neutral_pct": (neu / total) * 100.0,
            "negative_pct": (neg / total) * 100.0,
        },
        "keywords": {
            "top_keywords": [{"keyword": k, "count": c} for k, c in top_keywords],
        },
    }


def _sample_items(source: str, query: str, max_results: int) -> List[CollectedItem]:
    items: List[CollectedItem] = []
    for i in range(max_results):
        items.append(
            CollectedItem(
                source=source,
                title=f"{query} sample {i+1}",
                url=f"https://example.com/{source}/{i+1}",
                content=f"This is a sample content about {query} from {source}.",
                published_at=time.time(),
            )
        )
    return items


def _ts(v: Optional[str]) -> Optional[float]:
    try:
        # Naive conversion; acceptable for stub
        return time.time()
    except Exception:
        return None


