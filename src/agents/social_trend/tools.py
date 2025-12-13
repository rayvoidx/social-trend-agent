"""
Social Trend Agent Tools
"""
from __future__ import annotations

import time
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import logging

from src.integrations.mcp.sns_collect import fetch_x_posts_via_mcp
from src.integrations.mcp.news_collect import search_news_via_mcp
from src.core.config import get_config_manager
from src.core.utils import parse_timestamp, deduplicate_items
from src.integrations.retrieval.rag import RAGSystem
from src.integrations.llm.llm_client import get_llm_client
from src.core.refine import RefineEngine
from src.core.prompts import REPORT_GENERATION_PROMPT_TEMPLATE, DEFAULT_SYSTEM_PERSONA
from src.domain.schemas import TrendInsight
from src.core.routing import ModelRole, get_model_for_role

logger = logging.getLogger(__name__)

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
    """
    # MCP 서버를 통해서만 X 데이터를 가져옵니다.
    raw = fetch_x_posts_via_mcp(query=query, max_results=max_results * 2) # 중복 제거 고려하여 넉넉히 요청
    
    # 중복 제거 (URL, ID 기준)
    unique_raw = deduplicate_items(raw, unique_keys=["url", "id", "tweet_id"])
    
    items: List[CollectedItem] = []
    for t in unique_raw[:max_results]:
        items.append(
            CollectedItem(
                source="x",
                title=t.get("title", ""),
                url=t.get("url", ""),
                content=t.get("content", ""),
                published_at=parse_timestamp(t.get("created_at")),
            )
        )
    
    # MCP 결과가 비어 있는 경우 처리
    if not items:
        # 설정에 따라 샘플 데이터 허용 여부 결정
        if get_config_manager().should_allow_sample_fallback():
            logger.warning(f"Using sample X data for query: {query}")
            return _sample_items("x", query, max_results)
        else:
            logger.info("No X posts found and sample fallback disabled.")
            return []
            
    return items


def fetch_instagram_posts(query: str, max_results: int = 20) -> List[CollectedItem]:
    """
    Instagram에서 포스트를 가져옵니다.
    
    현재 실제 API 구현이 없으므로, 설정에 따라 샘플 데이터를 반환하거나 빈 리스트를 반환합니다.
    """
    if get_config_manager().should_allow_sample_fallback():
        logger.warning(f"Using sample Instagram data for query: {query}")
        return _sample_items("instagram", query, max_results)
    else:
        # 운영 환경에서 실제 구현 없으면 수집 안 함
        return []


def fetch_naver_blog_posts(query: str, max_results: int = 20) -> List[CollectedItem]:
    """
    네이버 블로그에서 포스트를 가져옵니다.
    """
    # Naver Blog도 MCP 기반 웹/뉴스 검색으로만 수집
    results = search_news_via_mcp(
        query=f"site:blog.naver.com {query}",
        time_window="7d",
        language="ko",
        max_results=max_results * 2,
    )
    
    unique_results = deduplicate_items(results, unique_keys=["url", "link"])
    
    items: List[CollectedItem] = []
    for r in unique_results[:max_results]:
        items.append(
            CollectedItem(
                source="naver_blog",
                title=r.get("title", ""),
                url=r.get("url", "") or r.get("link", ""),
                content=r.get("description", "") or r.get("content", ""),
                published_at=parse_timestamp(r.get("published_at") or r.get("pubDate")),
            )
        )
    
    if not items:
        if get_config_manager().should_allow_sample_fallback():
            logger.warning(f"Using sample Naver Blog data for query: {query}")
            return _sample_items("naver_blog", query, max_results)
        else:
            logger.info("No Naver Blog posts found and sample fallback disabled.")
            return []
            
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
            entries = parsed.get("entries", [])
            
            # RSS 항목도 중복 제거 필요하지만 feedparser 객체 구조상 복잡하므로 
            # 여기서는 간단히 처리하고 나중에 전체 병합 시 다시 체크
            
            for e in entries:
                if len(collected) >= max_results:
                    break
                    
                collected.append(
                    CollectedItem(
                        source="rss",
                        title=e.get("title", "")[:120],
                        url=e.get("link", ""),
                        content=e.get("summary", ""),
                        published_at=parse_timestamp(e.get("published")),
                    )
                )
        except Exception:
            continue
        if len(collected) >= max_results:
            break
            
    return collected


def normalize_items(items: List[Any]) -> List[Dict[str, Any]]:
    """
    수집된 아이템을 정규화된 딕셔너리 형태로 변환합니다.
    """
    normalized: List[Dict[str, Any]] = []
    for it in items:
        # Handle dictionary
        if isinstance(it, dict):
            normalized.append(it)
            continue
            
        # Handle CollectedItem object
        normalized.append(
            {
                "source": getattr(it, "source", "unknown"),
                "title": getattr(it, "title", ""),
                "url": getattr(it, "url", ""),
                "content": getattr(it, "content", ""),
                "published_at": getattr(it, "published_at", None),
            }
        )
    return normalized


def analyze_sentiment_and_keywords(texts: List[str], use_llm: bool = True) -> Dict[str, Any]:
    """
    텍스트 목록에서 감성과 키워드를 분석합니다. (LLM 또는 키워드 기반)
    """
    if use_llm:
        try:
            return _analyze_sentiment_llm(texts)
        except Exception as e:
            logger.warning(f"LLM sentiment analysis failed: {e}. Falling back to keyword based.")
    
    return _analyze_sentiment_keyword(texts)


def _analyze_sentiment_llm(texts: List[str]) -> Dict[str, Any]:
    """LLM 기반 감성 및 키워드 분석 (ModelRole.SENTIMENT 사용)"""
    client = get_llm_client()
    
    # 텍스트가 너무 많으면 샘플링
    sample_texts = texts[:30] if len(texts) > 30 else texts
    combined_text = "\n".join([f"- {t[:200]}" for t in sample_texts])
    
    prompt = f"""
    Analyze the sentiment and extract key topics from the following social media posts.
    
    Posts:
    {combined_text}
    
    Return JSON format:
    {{
        "sentiment": {{
            "positive": <count>,
            "neutral": <count>,
            "negative": <count>,
            "positive_pct": <float>,
            "neutral_pct": <float>,
            "negative_pct": <float>
        }},
        "keywords": {{
            "top_keywords": [
                {{"keyword": "word1", "count": 10}},
                {{"keyword": "word2", "count": 5}}
            ]
        }}
    }}
    """
    
    result = client.chat_json(
        messages=[
            {"role": "system", "content": "You are a social media sentiment analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        model=get_model_for_role("social_trend_agent", ModelRole.SENTIMENT),  # Model Routing
    )
    
    return result


def _analyze_sentiment_keyword(texts: List[str]) -> Dict[str, Any]:
    """키워드 기반 분석 (폴백)"""
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


def generate_trend_report(
    query: str,
    normalized: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    sources: List[str],
    time_window: str,
    strategy: str = "auto",
) -> str:
    """
    LLM을 사용하여 심층 트렌드 리포트를 생성합니다. (ModelRole.WRITER + RefineEngine)
    """
    logger.info(f"Generating trend report for: {query}")
    
    client = get_llm_client()
    engine = RefineEngine(client)
    writer_model = get_model_for_role("social_trend_agent", ModelRole.WRITER)
    synthesizer_model = get_model_for_role("social_trend_agent", ModelRole.SYNTHESIZER)
    
    sentiment = analysis.get("sentiment", {})
    keywords_data = analysis.get("keywords", {})
    top_keywords = keywords_data.get("top_keywords", [])
    
    keywords_str = ", ".join([kw['keyword'] for kw in top_keywords[:10]])
    
    # 헤드라인 추출 (Social post title or content snippet)
    headlines = []
    for item in normalized[:5]:
        content = item.get("title") or item.get("content") or ""
        headlines.append(f"- [{item.get('source')}] {content[:100]}...")
    headlines_str = "\n".join(headlines)
    
    prompt = REPORT_GENERATION_PROMPT_TEMPLATE.format(
        system_persona=DEFAULT_SYSTEM_PERSONA,
        query=query,
        positive_pct=sentiment.get('positive_pct', 0),
        negative_pct=sentiment.get('negative_pct', 0),
        neutral_pct=sentiment.get('neutral_pct', 0),
        keywords_str=keywords_str,
        headlines_str=headlines_str
    )
    
    try:
        routed = (analysis or {}).get("_routing") if isinstance(analysis, dict) else None
        if strategy == "auto" and isinstance(routed, dict):
            strategy = str(routed.get("summary_strategy") or "auto")

        if str(strategy).lower() == "cheap":
            # Cheap path: synthesizer-only brief, grounded in headlines/keywords.
            cheap_prompt = (
                "Write a compact Korean social trend brief.\n"
                "Requirements:\n"
                "- 6~10 bullets\n"
                "- No speculation; if uncertain, say '불확실'\n"
                "- Mention the most relevant keywords\n\n"
                f"Query: {query}\n"
                f"Time window: {time_window}\n"
                f"Sources: {', '.join(sources)}\n"
                f"Sentiment: {json.dumps(sentiment, ensure_ascii=False)}\n"
                f"Keywords: {keywords_str}\n"
                f"Headlines:\n{headlines_str}\n"
            )
            return client.chat(
                messages=[
                    {"role": "system", "content": "You are a cheap gateway summarizer. Be concise and grounded."},
                    {"role": "user", "content": cheap_prompt},
                ],
                temperature=0.3,
                max_tokens=900,
                model=synthesizer_model,
            ).strip()

        insight: TrendInsight = engine.refine_loop(
            prompt=prompt,
            initial_schema=TrendInsight,
            criteria="소셜 미디어 특성을 반영한 대중의 반응 분석, 구체적인 마케팅/대응 전략 포함",
            max_iterations=1,
            model=writer_model,  # Model Routing
        )
        
        return f"""
### 소셜 트렌드 요약
{insight.summary}

### 주요 반응 및 발견
{chr(10).join([f"- {item}" for item in insight.key_findings])}

### 실행 권고안 (마케팅/대응)
{chr(10).join([f"- {item}" for item in insight.recommendations])}

### 핵심 키워드
{", ".join(insight.keywords)}

---
*영향력 점수: {insight.impact_score}/10*
"""
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return "리포트 생성에 실패했습니다."


def retrieve_relevant_posts(
    query: str,
    items: List[Dict[str, Any]],
    top_k: int = 10,
    use_graph: bool = True,
) -> List[Dict[str, Any]]:
    """
    RAG 기반 관련성 높은 포스트 필터링.
    """
    # 1. RAG 시스템 초기화
    rag = RAGSystem("social_trend_agent")
    
    # 2. RAG 비활성화 시 키워드 폴백
    if not rag.is_enabled():
        return _retrieve_relevant_items_keyword(query, items, top_k)
        
    try:
        # 3. 문서 인덱싱 (간단 구현: 매번 새로 인덱싱)
        documents = []
        for it in items:
            text = f"{it.get('title','')} {it.get('content','')} {it.get('source','')}"
            documents.append(text)
            
        if not documents:
            return []
            
        rag.index_documents(documents, items)
        
        # 4. 검색
        results = rag.retrieve(query, top_k, use_graph=use_graph)
        
        if not results:
            return _retrieve_relevant_items_keyword(query, items, top_k)
            
        return results
        
    except Exception as e:
        logger.warning(f"RAG retrieval failed: {e}")
        return _retrieve_relevant_items_keyword(query, items, top_k)


def _retrieve_relevant_items_keyword(
    query: str,
    items: List[Dict[str, Any]],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """키워드 기반 단순 검색 (폴백)"""
    tokens = [t for t in re.split(r"[^0-9A-Za-z가-힣]+", (query or "").lower()) if len(t) > 1]
    
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for it in items:
        text = f"{it.get('title','')} {it.get('content','')}".lower()
        score = sum(1 for tok in tokens if tok in text)
        scored.append((score, it))
        
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:max(1, top_k)]]


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
