"""
Tools for News Trend Agent
"""
import os
import time
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests


# ============================================================================
# Data Collection Tools
# ============================================================================

def search_news(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Search news from News API and Naver News API

    Args:
        query: Search keyword
        time_window: Time window (e.g., "24h", "7d", "30d")
        language: Language code ("ko", "en")
        max_results: Maximum number of results

    Returns:
        List of news items with title, description, url, source, publishedAt
    """
    print(f"[search_news] query={query}, time_window={time_window}, language={language}")

    news_items = []

    # Parse time window
    from_date = _parse_time_window(time_window)

    # Try News API (global news)
    news_api_key = os.getenv("NEWS_API_KEY")
    if news_api_key and language == "en":
        news_items.extend(_search_news_api(query, from_date, news_api_key, max_results))

    # Try Naver News API (Korean news)
    naver_client_id = os.getenv("NAVER_CLIENT_ID")
    naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")
    if naver_client_id and naver_client_secret and language == "ko":
        news_items.extend(_search_naver_news(query, naver_client_id, naver_client_secret, max_results))

    # Fallback to sample data if no API keys
    if not news_items:
        print("[search_news] No API keys found, using sample data")
        news_items = _get_sample_news(query, time_window, language)

    return news_items[:max_results]


def _parse_time_window(time_window: str) -> str:
    """Parse time window string to datetime"""
    now = datetime.now()

    if time_window.endswith("h"):
        hours = int(time_window[:-1])
        from_date = now - timedelta(hours=hours)
    elif time_window.endswith("d"):
        days = int(time_window[:-1])
        from_date = now - timedelta(days=days)
    else:
        from_date = now - timedelta(days=7)

    return from_date.strftime("%Y-%m-%d")


def _search_news_api(query: str, from_date: str, api_key: str, max_results: int) -> List[Dict[str, Any]]:
    """Search news using News API"""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": from_date,
        "sortBy": "publishedAt",
        "apiKey": api_key,
        "pageSize": max_results,
        "language": "en"
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("articles", [])
    except Exception as e:
        print(f"[_search_news_api] Error: {e}")
        return []


def _search_naver_news(query: str, client_id: str, client_secret: str, max_results: int) -> List[Dict[str, Any]]:
    """Search news using Naver News API"""
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": query,
        "display": max_results,
        "sort": "date"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Convert Naver format to News API format
        articles = []
        for item in data.get("items", []):
            articles.append({
                "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                "description": item.get("description", "").replace("<b>", "").replace("</b>", ""),
                "url": item.get("link", ""),
                "source": {"name": "Naver News"},
                "publishedAt": item.get("pubDate", ""),
                "content": item.get("description", "")
            })

        return articles
    except Exception as e:
        print(f"[_search_naver_news] Error: {e}")
        return []


def _get_sample_news(query: str, time_window: str, language: str) -> List[Dict[str, Any]]:
    """Generate sample news data for testing"""
    now = datetime.now()

    sample_news = [
        {
            "title": f"{query} 관련 최신 뉴스 1" if language == "ko" else f"Latest news about {query} 1",
            "description": f"{query}에 대한 분석 내용입니다." if language == "ko" else f"Analysis about {query}.",
            "url": "https://example.com/news1",
            "source": {"name": "Sample News"},
            "publishedAt": (now - timedelta(hours=2)).isoformat(),
            "content": f"{query} 관련 상세 내용" if language == "ko" else f"Detailed content about {query}"
        },
        {
            "title": f"{query} 트렌드 급상승" if language == "ko" else f"{query} trending up",
            "description": f"{query} 관련 검색량이 증가하고 있습니다." if language == "ko" else f"Search volume for {query} is increasing.",
            "url": "https://example.com/news2",
            "source": {"name": "Sample News"},
            "publishedAt": (now - timedelta(hours=5)).isoformat(),
            "content": f"{query} 트렌드 분석" if language == "ko" else f"Trend analysis of {query}"
        },
        {
            "title": f"{query} 시장 반응" if language == "ko" else f"Market reaction to {query}",
            "description": f"{query}에 대한 소비자 반응이 긍정적입니다." if language == "ko" else f"Consumer reaction to {query} is positive.",
            "url": "https://example.com/news3",
            "source": {"name": "Sample News"},
            "publishedAt": (now - timedelta(days=1)).isoformat(),
            "content": f"{query} 시장 분석" if language == "ko" else f"Market analysis of {query}"
        }
    ]

    return sample_news


# ============================================================================
# Analysis Tools
# ============================================================================

def analyze_sentiment(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze sentiment of news items

    Args:
        items: List of normalized news items

    Returns:
        Sentiment analysis results (positive, neutral, negative counts)
    """
    print(f"[analyze_sentiment] Analyzing {len(items)} items...")

    # Simple keyword-based sentiment (production: use Azure OpenAI)
    positive_keywords = ["긍정", "성공", "성장", "증가", "호평", "positive", "success", "growth", "increase"]
    negative_keywords = ["부정", "실패", "감소", "하락", "비판", "negative", "failure", "decrease", "decline"]

    positive_count = 0
    neutral_count = 0
    negative_count = 0

    for item in items:
        text = (item.get("title", "") + " " + item.get("description", "")).lower()

        has_positive = any(kw in text for kw in positive_keywords)
        has_negative = any(kw in text for kw in negative_keywords)

        if has_positive and not has_negative:
            positive_count += 1
        elif has_negative and not has_positive:
            negative_count += 1
        else:
            neutral_count += 1

    total = len(items)

    return {
        "positive": positive_count,
        "neutral": neutral_count,
        "negative": negative_count,
        "positive_pct": (positive_count / total * 100) if total > 0 else 0,
        "neutral_pct": (neutral_count / total * 100) if total > 0 else 0,
        "negative_pct": (negative_count / total * 100) if total > 0 else 0
    }


def extract_keywords(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract keywords from news items

    Args:
        items: List of normalized news items

    Returns:
        Keyword extraction results (top keywords, frequency)
    """
    print(f"[extract_keywords] Extracting keywords from {len(items)} items...")

    # Simple word frequency (production: use TF-IDF or LLM)
    word_freq = {}
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "을", "를", "이", "가", "은", "는", "에", "의"}

    for item in items:
        text = (item.get("title", "") + " " + item.get("description", "")).lower()
        words = text.split()

        for word in words:
            word = word.strip(".,!?\"'")
            if len(word) > 2 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1

    # Sort by frequency
    sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    top_keywords = [
        {"keyword": kw, "count": count}
        for kw, count in sorted_keywords[:20]
    ]

    return {
        "top_keywords": top_keywords,
        "total_unique_keywords": len(word_freq)
    }


def summarize_trend(
    query: str,
    normalized_items: List[Dict[str, Any]],
    analysis: Dict[str, Any]
) -> str:
    """
    Summarize trend insights using LLM

    Args:
        query: Original search query
        normalized_items: Normalized news items
        analysis: Analysis results (sentiment, keywords)

    Returns:
        Trend summary text
    """
    print(f"[summarize_trend] Summarizing trend for query={query}...")

    # TODO: Use Azure OpenAI for real summarization
    # For now, generate simple summary

    sentiment = analysis.get("sentiment", {})
    keywords = analysis.get("keywords", {}).get("top_keywords", [])

    summary_lines = []

    # Overall sentiment
    if sentiment.get("positive_pct", 0) > 50:
        summary_lines.append(f"'{query}'에 대한 전반적인 반응은 **긍정적**입니다.")
    elif sentiment.get("negative_pct", 0) > 50:
        summary_lines.append(f"'{query}'에 대한 전반적인 반응은 **부정적**입니다.")
    else:
        summary_lines.append(f"'{query}'에 대한 반응은 **중립적**입니다.")

    # Top keywords
    if keywords:
        top_3 = [kw["keyword"] for kw in keywords[:3]]
        summary_lines.append(f"주요 키워드: {', '.join(top_3)}")

    # Action recommendations
    summary_lines.append("")
    summary_lines.append("**실행 권고안:**")
    summary_lines.append("- 긍정 반응이 높은 콘텐츠를 중심으로 마케팅 전략 수립")
    summary_lines.append("- 주요 키워드를 활용한 SEO 최적화")
    summary_lines.append("- 부정 반응이 있는 경우, 원인 분석 및 개선 방안 마련")

    return "\n".join(summary_lines)
