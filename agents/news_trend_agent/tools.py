"""
뉴스 트렌드 에이전트를 위한 도구

Phase 3 유틸리티 통합: 재시도, 캐싱, 로깅
"""
import os
import time
from typing import List, Dict, Any
from datetime import datetime, timedelta
import requests

# Phase 3 utilities
from agents.shared.retry import backoff_retry, retry_on_rate_limit
from agents.shared.cache import cached
from agents.shared.logging import AgentLogger

# LangChain for LLM integration
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Initialize logger
logger = AgentLogger("news_trend_agent")


# ============================================================================
# Data Collection Tools
# ============================================================================

@cached(ttl=3600, use_disk=False)  # 1시간 동안 캐싱
def search_news(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    News API 및 Naver News API에서 뉴스 검색

    1시간 이내 중복 API 호출을 방지하기 위해 캐싱을 사용합니다.

    Args:
        query: 검색 키워드
        time_window: 시간 범위 (예: "24h", "7d", "30d")
        language: 언어 코드 ("ko", "en")
        max_results: 최대 결과 수

    Returns:
        title, description, url, source, publishedAt을 포함한 뉴스 항목 리스트
    """
    logger.info("Searching news", query=query, time_window=time_window, language=language, max_results=max_results)

    news_items = []

    # Parse time window
    from_date = _parse_time_window(time_window)

    # Try News API (global news)
    news_api_key = os.getenv("NEWS_API_KEY")
    if news_api_key and language == "en":
        logger.info("Using News API")
        news_items.extend(_search_news_api(query, from_date, news_api_key, max_results))

    # Try Naver News API (Korean news)
    naver_client_id = os.getenv("NAVER_CLIENT_ID")
    naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")
    if naver_client_id and naver_client_secret and language == "ko":
        logger.info("Using Naver News API")
        news_items.extend(_search_naver_news(query, naver_client_id, naver_client_secret, max_results))

    # Fallback to sample data if no API keys
    if not news_items:
        logger.warning("No API keys found, using sample data")
        news_items = _get_sample_news(query, time_window, language)

    logger.info("News search completed", total_results=len(news_items))
    return news_items[:max_results]


def _parse_time_window(time_window: str) -> str:
    """시간 범위 문자열을 datetime으로 파싱"""
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


@backoff_retry(max_retries=3, backoff_factor=0.5)
@retry_on_rate_limit(max_retries=3)
def _search_news_api(query: str, from_date: str, api_key: str, max_results: int) -> List[Dict[str, Any]]:
    """
    News API를 사용한 뉴스 검색

    일시적 실패 및 API 제한에 대한 재시도 로직을 포함합니다.
    """
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
        articles = data.get("articles", [])
        logger.info("News API search completed", article_count=len(articles))
        return articles
    except requests.exceptions.HTTPError as e:
        logger.error("News API HTTP error", status_code=e.response.status_code, error=str(e))
        raise
    except Exception as e:
        logger.error("News API error", error=str(e))
        return []


@backoff_retry(max_retries=3, backoff_factor=0.5)
@retry_on_rate_limit(max_retries=3)
def _search_naver_news(query: str, client_id: str, client_secret: str, max_results: int) -> List[Dict[str, Any]]:
    """
    Naver News API를 사용한 뉴스 검색

    일시적 실패 및 API 제한에 대한 재시도 로직을 포함합니다.
    """
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

        logger.info("Naver News API search completed", article_count=len(articles))
        return articles
    except requests.exceptions.HTTPError as e:
        logger.error("Naver News API HTTP error", status_code=e.response.status_code, error=str(e))
        raise
    except Exception as e:
        logger.error("Naver News API error", error=str(e))
        return []


def _get_sample_news(query: str, time_window: str, language: str) -> List[Dict[str, Any]]:
    """테스트용 샘플 뉴스 데이터 생성"""
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
    뉴스 항목의 감성 분석

    Args:
        items: 정규화된 뉴스 항목 리스트

    Returns:
        감성 분석 결과 (긍정, 중립, 부정 개수)
    """
    logger.info("Starting sentiment analysis", item_count=len(items))

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

    result = {
        "positive": positive_count,
        "neutral": neutral_count,
        "negative": negative_count,
        "positive_pct": (positive_count / total * 100) if total > 0 else 0,
        "neutral_pct": (neutral_count / total * 100) if total > 0 else 0,
        "negative_pct": (negative_count / total * 100) if total > 0 else 0
    }

    logger.info("Sentiment analysis completed", result=result)
    return result


def extract_keywords(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    뉴스 항목에서 키워드 추출

    Args:
        items: 정규화된 뉴스 항목 리스트

    Returns:
        키워드 추출 결과 (상위 키워드, 빈도)
    """
    logger.info("Starting keyword extraction", item_count=len(items))

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

    result = {
        "top_keywords": top_keywords,
        "total_unique_keywords": len(word_freq)
    }

    logger.info("Keyword extraction completed", unique_keywords=len(word_freq))
    return result


def _get_llm():
    """
    LLM_PROVIDER 환경 변수에 따른 LLM 인스턴스 반환

    멀티 프로바이더 지원을 위한 LangChain 공식 패턴을 따릅니다.
    """
    provider = os.getenv("LLM_PROVIDER", "azure_openai").lower()

    logger.info("Initializing LLM", provider=provider)

    if provider == "azure_openai":
        return AzureChatOpenAI(
            deployment_name=os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-4"),
            temperature=0.7,
            max_tokens=1000
        )
    elif provider == "openai":
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL_NAME", "gpt-4-turbo-preview"),
            temperature=0.7,
            max_tokens=1000
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229"),
            temperature=0.7,
            max_tokens=1000
        )
    elif provider == "google":
        return ChatGoogleGenerativeAI(
            model=os.getenv("GOOGLE_MODEL_NAME", "gemini-pro"),
            temperature=0.7,
            max_tokens=1000
        )
    else:
        # Fallback to Azure OpenAI
        logger.warning(f"Unknown LLM provider '{provider}', falling back to Azure OpenAI")
        return AzureChatOpenAI(
            deployment_name=os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-4"),
            temperature=0.7,
            max_tokens=1000
        )


@backoff_retry(max_retries=3, backoff_factor=1.0)
def summarize_trend(
    query: str,
    normalized_items: List[Dict[str, Any]],
    analysis: Dict[str, Any]
) -> str:
    """
    LLM을 활용한 트렌드 인사이트 요약

    LCEL(LangChain Expression Language)을 사용하는 LangChain 공식 패턴을 적용합니다.

    Args:
        query: 원본 검색 쿼리
        normalized_items: 정규화된 뉴스 항목
        analysis: 분석 결과 (감성, 키워드)

    Returns:
        LLM이 생성한 트렌드 요약 텍스트
    """
    logger.info("Starting trend summarization", query=query, item_count=len(normalized_items))

    sentiment = analysis.get("sentiment", {})
    keywords = analysis.get("keywords", {}).get("top_keywords", [])

    # Extract top 5 news headlines
    top_headlines = [item.get("title", "") for item in normalized_items[:5]]

    # Build context for LLM
    keywords_str = ", ".join([kw["keyword"] for kw in keywords[:10]])
    headlines_str = "\n".join([f"- {headline}" for headline in top_headlines])

    # Create prompt using LangChain ChatPromptTemplate (official pattern)
    prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 소비자 트렌드 분석 전문가입니다.
주어진 뉴스 데이터를 분석하여 마케팅 및 상품 기획팀이 활용할 수 있는 핵심 인사이트를 제공하세요.

응답 형식:
1. 전반적인 트렌드 요약 (2-3문장)
2. 주요 발견사항 (3-5개 bullet points)
3. 실행 가능한 권고안 (3-5개 bullet points)

명확하고 실용적인 분석을 제공하세요."""),
        ("user", """다음 데이터를 분석해주세요:

**검색어**: {query}

**감성 분석 결과**:
- 긍정: {positive}건 ({positive_pct:.1f}%)
- 중립: {neutral}건 ({neutral_pct:.1f}%)
- 부정: {negative}건 ({negative_pct:.1f}%)

**주요 키워드**: {keywords}

**주요 뉴스 헤드라인**:
{headlines}

위 데이터를 바탕으로 트렌드 분석 리포트를 작성하세요.""")
    ])

    try:
        # Get LLM instance
        llm = _get_llm()

        # Create chain using LCEL (LangChain Expression Language) - official pattern
        chain = prompt | llm | StrOutputParser()

        # Invoke chain
        summary = chain.invoke({
            "query": query,
            "positive": sentiment.get("positive", 0),
            "neutral": sentiment.get("neutral", 0),
            "negative": sentiment.get("negative", 0),
            "positive_pct": sentiment.get("positive_pct", 0),
            "neutral_pct": sentiment.get("neutral_pct", 0),
            "negative_pct": sentiment.get("negative_pct", 0),
            "keywords": keywords_str,
            "headlines": headlines_str
        })

        logger.info("Trend summarization completed", summary_length=len(summary))
        return summary

    except Exception as e:
        logger.error("Error in LLM summarization, falling back to simple summary", error=str(e))

        # Fallback to simple summary
        summary_lines = []

        if sentiment.get("positive_pct", 0) > 50:
            summary_lines.append(f"'{query}'에 대한 전반적인 반응은 **긍정적**입니다.")
        elif sentiment.get("negative_pct", 0) > 50:
            summary_lines.append(f"'{query}'에 대한 전반적인 반응은 **부정적**입니다.")
        else:
            summary_lines.append(f"'{query}'에 대한 반응은 **중립적**입니다.")

        if keywords:
            top_3 = [kw["keyword"] for kw in keywords[:3]]
            summary_lines.append(f"\n주요 키워드: {', '.join(top_3)}")

        summary_lines.append("\n**실행 권고안:**")
        summary_lines.append("- 긍정 반응이 높은 콘텐츠를 중심으로 마케팅 전략 수립")
        summary_lines.append("- 주요 키워드를 활용한 SEO 최적화")
        summary_lines.append("- 부정 반응이 있는 경우, 원인 분석 및 개선 방안 마련")

        return "\n".join(summary_lines)
