"""
뉴스 트렌드 에이전트를 위한 도구

Phase 3 유틸리티 통합: 재시도, 캐싱, 로깅
Phase 6 구조화 출력 및 Self-Refine
Phase 10 컨텍스트 프롬프트 고도화 (Wrtn Style)
"""
import os
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
import re

# Phase 3 utilities
from src.infrastructure.retry import backoff_retry
from src.infrastructure.cache import cached
from src.core.config import get_config_manager
from src.core.utils import parse_timestamp, deduplicate_items
from src.core.refine import RefineEngine
from src.core.prompts import REPORT_GENERATION_PROMPT_TEMPLATE, DEFAULT_SYSTEM_PERSONA # Phase 10
from src.core.routing import ModelRole, get_model_for_role
from src.domain.plan import AgentPlan
from src.domain.schemas import TrendInsight
from src.integrations.retrieval.rag import RAGSystem
from src.integrations.mcp.news_collect import search_news_via_mcp
from src.integrations.llm import get_llm_client

# LangChain for LLM integration (뉴스 에이전트는 LangChain 기반 요약 체인을 유지)
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI

# Initialize module-level logger (without run_id for module-level logging)
logger = logging.getLogger("news_trend_agent")


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
    logger.info(
        f"Searching news via MCP: query={query}, time_window={time_window}, language={language}, max_results={max_results}"
    )

    # MCP 서버(brave-search 등)를 통해서만 뉴스 검색을 수행
    # 중복 제거를 위해 max_results보다 넉넉하게 요청
    news_items = search_news_via_mcp(
        query=query,
        time_window=time_window,
        language=language,
        max_results=max_results * 2,
    )

    # MCP 결과가 없으면 설정에 따라 샘플 데이터로 폴백하거나 빈 결과 반환
    if not news_items:
        if get_config_manager().should_allow_sample_fallback():
            logger.warning("No news items from MCP, using sample data")
            news_items = _get_sample_news(query, time_window, language)
        else:
            logger.info("No news items found and sample fallback disabled.")
            return []

    # 중복 제거
    unique_items = deduplicate_items(news_items, unique_keys=["url", "link", "id"])
    
    # 타임스탬프 파싱 및 데이터 정규화
    final_items = []
    for item in unique_items[:max_results]:
        # 날짜 파싱 (기존 publishedAt은 유지하고 parsed_timestamp 추가)
        pub_str = item.get("publishedAt") or item.get("published_at") or item.get("pubDate")
        ts = parse_timestamp(pub_str)
        
        item["published_timestamp"] = ts
        if not item.get("publishedAt") and pub_str:
             item["publishedAt"] = pub_str # Ensure publishedAt exists if we found it elsewhere
             
        final_items.append(item)

    logger.info(f"News search completed: total_results={len(final_items)}")
    return final_items


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

def analyze_sentiment(items: List[Dict[str, Any]], use_llm: bool = True) -> Dict[str, Any]:
    """
    뉴스 항목의 감성 분석

    Args:
        items: 정규화된 뉴스 항목 리스트
        use_llm: LLM 기반 분석 사용 여부 (기본값: True)

    Returns:
        감성 분석 결과 (긍정, 중립, 부정 개수)
    """
    logger.info(f"Starting sentiment analysis: item_count={len(items)}, use_llm={use_llm}")

    if not items:
        return {
            "positive": 0, "neutral": 0, "negative": 0,
            "positive_pct": 0, "neutral_pct": 0, "negative_pct": 0
        }

    # LLM 기반 감성 분석
    if use_llm:
        try:
            return _analyze_sentiment_llm(items)
        except Exception as e:
            logger.warning(f"LLM sentiment analysis failed, falling back to keyword-based: {e}")

    # 키워드 기반 폴백
    return _analyze_sentiment_keyword(items)


def _analyze_sentiment_llm(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 기반 감성 분석"""
    # client = get_llm_client() # Already imported at top level

    client = get_llm_client()

    # Prepare texts for analysis
    texts = []
    for item in items[:30]:  # Limit to 30 items for LLM
        text = f"{item.get('title', '')} - {item.get('description', '')[:200]}"
        texts.append(text)

    prompt = f"""Analyze the sentiment of each text and provide counts.

Texts:
{chr(10).join([f'{i+1}. {text}' for i, text in enumerate(texts)])}

Return JSON format:
{{
    "positive": <count>,
    "neutral": <count>,
    "negative": <count>,
    "sentiment_details": [
        {{"index": 0, "sentiment": "positive"|"neutral"|"negative", "confidence": 0.0-1.0}}
    ],
    "key_emotions": ["emotion1", "emotion2"],
    "summary": "brief overall sentiment summary"
}}"""

    sentiment_model = get_model_for_role("news_trend_agent", ModelRole.SENTIMENT)
    result = client.chat_json(
        messages=[
            {"role": "system", "content": "You are a sentiment analysis expert. Analyze Korean and English text accurately."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        model=sentiment_model  # Model Routing: sentiment role (safe fallback handled in llm_client)
    )

    total = len(items)
    positive = result.get("positive", 0)
    neutral = result.get("neutral", 0)
    negative = result.get("negative", 0)

    analyzed_total = positive + neutral + negative
    if analyzed_total == 0:
        analyzed_total = total

    return {
        "positive": positive,
        "neutral": neutral,
        "negative": negative,
        "positive_pct": (positive / analyzed_total * 100) if analyzed_total > 0 else 0,
        "neutral_pct": (neutral / analyzed_total * 100) if analyzed_total > 0 else 0,
        "negative_pct": (negative / analyzed_total * 100) if analyzed_total > 0 else 0,
        "key_emotions": result.get("key_emotions", []),
        "summary": result.get("summary", ""),
        "details": result.get("sentiment_details", [])
    }


def _analyze_sentiment_keyword(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """키워드 기반 감성 분석 (폴백)"""
    positive_keywords = ["긍정", "성공", "성장", "증가", "호평", "좋", "기대", "상승",
                        "positive", "success", "growth", "increase", "good", "excellent"]
    negative_keywords = ["부정", "실패", "감소", "하락", "비판", "우려", "하락", "문제",
                        "negative", "failure", "decrease", "decline", "bad", "concern"]

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


def extract_keywords(items: List[Dict[str, Any]], use_tfidf: bool = True) -> Dict[str, Any]:
    """
    뉴스 항목에서 키워드 추출

    Args:
        items: 정규화된 뉴스 항목 리스트
        use_tfidf: TF-IDF 사용 여부 (기본값: True)

    Returns:
        키워드 추출 결과 (상위 키워드, 점수)
    """
    logger.info(f"Starting keyword extraction: item_count={len(items)}, use_tfidf={use_tfidf}")

    if not items:
        return {"top_keywords": [], "total_unique_keywords": 0}

    # TF-IDF 기반 키워드 추출
    if use_tfidf:
        try:
            return _extract_keywords_tfidf(items)
        except Exception as e:
            logger.warning(f"TF-IDF keyword extraction failed, falling back to frequency: {e}")

    # 빈도 기반 폴백
    return _extract_keywords_frequency(items)


def _extract_keywords_tfidf(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """TF-IDF 기반 키워드 추출"""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer # type: ignore[import]
        import numpy as np
    except ImportError:
        logger.warning("scikit-learn not installed, falling back to frequency-based")
        return _extract_keywords_frequency(items)

    # Prepare documents
    documents = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('description', '')} {item.get('content', '')}"
        documents.append(text)

    if not documents:
        return {"top_keywords": [], "total_unique_keywords": 0}

    # Korean + English stop words
    stop_words = [
        # Korean
        "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", "도", "로", "으로",
        "에서", "까지", "부터", "만", "뿐", "다", "고", "며", "면", "지", "든", "니",
        "하다", "있다", "되다", "이다", "그", "저", "이", "것", "수", "등", "및",
        # English
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "this", "that",
        "these", "those", "i", "you", "he", "she", "it", "we", "they",
        "what", "which", "who", "when", "where", "why", "how", "all",
        "each", "every", "both", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "just", "also", "now", "said", "says"
    ]

    # TF-IDF Vectorizer
    vectorizer = TfidfVectorizer(
        max_features=100,
        stop_words=stop_words,
        ngram_range=(1, 2),  # Unigrams and bigrams
        min_df=1,
        max_df=0.9,
        token_pattern=r'(?u)\b[가-힣a-zA-Z]{2,}\b'  # Korean + English, min 2 chars
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(documents)
        feature_names = vectorizer.get_feature_names_out()

        # Calculate average TF-IDF score across all documents
        avg_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()

        # Create keyword list with scores
        keyword_scores = list(zip(feature_names, avg_scores))
        keyword_scores.sort(key=lambda x: x[1], reverse=True)

        # Get top keywords
        top_keywords = [
            {"keyword": kw, "score": round(float(score), 4), "count": int((tfidf_matrix[:, i].toarray() > 0).sum())}
            for i, (kw, score) in enumerate(keyword_scores[:20])
            if score > 0.01
        ]

        # Also extract document frequency for reference
        doc_freq = {}
        for i, kw in enumerate(feature_names):
            doc_freq[kw] = int((tfidf_matrix[:, i].toarray() > 0).sum())

        return {
            "top_keywords": top_keywords,
            "total_unique_keywords": len(feature_names),
            "method": "tfidf",
            "ngram_range": "1-2"
        }

    except Exception as e:
        logger.error(f"TF-IDF vectorization failed: {e}")
        return _extract_keywords_frequency(items)


def _extract_keywords_frequency(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """빈도 기반 키워드 추출 (폴백)"""
    word_freq: Dict[str, int] = {}
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "have", "has",
        "을", "를", "이", "가", "은", "는", "에", "의", "와", "과", "도", "로",
        "this", "that", "it", "for", "on", "with", "as", "at", "by", "from"
    }

    for item in items:
        text = (item.get("title", "") + " " + item.get("description", "")).lower()
        # Simple tokenization
        words = re.findall(r'[가-힣a-zA-Z]{2,}', text)

        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1

    # Sort by frequency
    sorted_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    top_keywords = [
        {"keyword": kw, "count": count}
        for kw, count in sorted_keywords[:20]
    ]

    return {
        "top_keywords": top_keywords,
        "total_unique_keywords": len(word_freq),
        "method": "frequency"
    }


def _get_llm():
    """
    에이전트별 설정에 따른 LangChain LLM 인스턴스 반환.

    - config/default.yaml 의 agents.news_trend_agent.llm.provider / model_name 을 우선 사용
    - 없으면 전역 LLM_PROVIDER 및 관련 환경 변수를 사용
    """
    cfg = get_config_manager()
    agent_cfg = cfg.get_agent_config("news_trend_agent")

    # 기본 provider는 azure_openai (기존 코드 유지)
    provider = os.getenv("LLM_PROVIDER", "azure_openai").lower()
    model_name: Optional[str] = None

    if agent_cfg and agent_cfg.llm:
        if agent_cfg.llm.provider:
            provider = str(agent_cfg.llm.provider)
        model_name = agent_cfg.llm.model_name or None

    logger.info(f"Initializing LLM for news_trend_agent: provider={provider}, model={model_name or 'auto'}")

    if provider == "azure_openai" or provider == "azure":
        deployment_name = (
            agent_cfg.llm.deployment_name
            if agent_cfg and agent_cfg.llm and agent_cfg.llm.deployment_name
            else os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-5.2")
        )
        return AzureChatOpenAI(
            deployment_name=deployment_name,
            temperature=0.7,
            max_tokens=1000,
        )
    elif provider == "openai":
        # Ref: https://platform.openai.com/docs/models (GPT-4 Turbo Preview is deprecated)
        model = model_name or os.getenv("OPENAI_MODEL_NAME", "gpt-5.2")
        return ChatOpenAI(
            model=model,
            temperature=0.7,
            max_tokens=1000,
        )
    elif provider == "anthropic":
        # Ref: https://docs.anthropic.com/en/docs/about-claude/models
        model = model_name or os.getenv("ANTHROPIC_MODEL_NAME", "claude-sonnet-4-5")
        return ChatAnthropic(
            model=model,
            temperature=0.7,
            max_tokens=1000,
        )
    elif provider == "google":
        # Ref: https://ai.google.dev/gemini-api/docs/models
        model = model_name or os.getenv("GOOGLE_MODEL_NAME", "gemini-2.5-pro")
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0.7,
            max_tokens=1000,
        )
    else:
        # Fallback to Azure OpenAI
        logger.warning(f"Unknown LLM provider '{provider}', falling back to Azure OpenAI")
        deployment_name = os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-5.2")
        return AzureChatOpenAI(
            deployment_name=deployment_name,
            temperature=0.7,
            max_tokens=1000,
        )


@backoff_retry(max_retries=3, backoff_factor=1.0)
def summarize_trend(
    query: str,
    normalized_items: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    strategy: str = "auto",
) -> str:
    """
    LLM을 활용한 트렌드 인사이트 요약 (구조화된 출력 및 Self-Refine 적용)

    Args:
        query: 원본 검색 쿼리
        normalized_items: 정규화된 뉴스 항목
        analysis: 분석 결과 (감성, 키워드)

    Returns:
        LLM이 생성한 트렌드 요약 텍스트 (Markdown 형식)
    """
    logger.info(f"Starting trend summarization: query={query}, item_count={len(normalized_items)}")

    sentiment = analysis.get("sentiment", {})
    keywords = analysis.get("keywords", {}).get("top_keywords", [])

    # Extract top 5 news headlines
    top_headlines = [item.get("title", "") for item in normalized_items[:5]]

    # Build context for LLM
    keywords_str = ", ".join([kw["keyword"] for kw in keywords[:10]])
    headlines_str = "\n".join([f"- {headline}" for headline in top_headlines])

    # Phase 10: Use Enhanced Prompt Template
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
        # Router can pass strategy via analysis["_routing"]["summary_strategy"].
        routed = (analysis or {}).get("_routing") if isinstance(analysis, dict) else None
        if strategy == "auto" and isinstance(routed, dict):
            strategy = str(routed.get("summary_strategy") or "auto")

        client = get_llm_client()  # unified LLM client (provider decided by env/config)
        synthesizer_model = get_model_for_role("news_trend_agent", ModelRole.SYNTHESIZER)
        planner_model = get_model_for_role("news_trend_agent", ModelRole.PLANNER)
        writer_model = get_model_for_role("news_trend_agent", ModelRole.WRITER)

        # Prepare snippets (used in both paths)
        raw_snippets = []
        for it in normalized_items[: min(15, len(normalized_items))]:
            raw_snippets.append(
                {
                    "title": it.get("title", ""),
                    "url": it.get("url", ""),
                    "description": it.get("description", ""),
                    "publishedAt": it.get("publishedAt", ""),
                    "source": (it.get("source") or {}).get("name", ""),
                }
            )

        # Cheap path (SLM-style): synthesizer only
        if str(strategy).lower() == "cheap":
            synth_prompt = (
                "Create a compact Korean trend brief based ONLY on the provided snippets.\n"
                "Requirements:\n"
                "- Title + 6~10 bullets\n"
                "- Each bullet must include one URL in parentheses\n"
                "- No speculation; if uncertain, say '불확실'\n\n"
                f"Query: {query}\n\n"
                f"Snippets (JSON): {json.dumps(raw_snippets, ensure_ascii=False)}\n"
            )
            brief = client.chat(
                messages=[
                    {"role": "system", "content": "You are a cheap gateway summarizer. Be concise and grounded."},
                    {"role": "user", "content": synth_prompt},
                ],
                temperature=0.3,
                max_tokens=900,
                model=synthesizer_model,
            )
            return str(brief).strip()

        # Compound (2025): planner(JSON) -> synthesizer(cheap) -> writer(refine)
        plan_prompt = (
            "You are a planner for a trend-analysis agent. "
            "Return ONLY JSON that matches the schema.\n\n"
            f"Query: {query}\n"
            f"Language: ko\n"
            f"Signals:\n"
            f"- Sentiment: {sentiment}\n"
            f"- Top keywords: {[kw.get('keyword') for kw in keywords[:10]]}\n"
            f"- Headlines (top): {top_headlines}\n"
        )

        plan_dict = client.chat_json(
            messages=[
                {"role": "system", "content": "You are a strict planning engine. Output JSON only."},
                {"role": "user", "content": plan_prompt},
            ],
            schema=AgentPlan.model_json_schema(),
            temperature=0.2,
            model=planner_model,
            max_tokens=700,
        )
        plan = AgentPlan.model_validate(plan_dict)

        synth_prompt = (
            "Summarize the following news snippets into a compact Korean brief.\n"
            "Requirements:\n"
            "- 6~10 bullets max\n"
            "- Each bullet must reference at least one title and include URL in parentheses\n"
            "- No speculation; if uncertain, say '불확실'\n\n"
            f"Query: {query}\n\n"
            f"Snippets (JSON): {json.dumps(raw_snippets, ensure_ascii=False)}\n"
        )

        synthesized_context = client.chat(
            messages=[
                {"role": "system", "content": "You are a context synthesizer. Be concise and factual."},
                {"role": "user", "content": synth_prompt},
            ],
            temperature=0.3,
            max_tokens=900,
            model=synthesizer_model,
        )

        engine = RefineEngine(client)
        compound_prompt = (
            prompt
            + "\n\n---\n"
            + "## Planner Output (JSON)\n"
            + plan.model_dump_json(indent=2)
            + "\n\n---\n"
            + "## Synthesized Context (grounded)\n"
            + str(synthesized_context)
        )

        insight: TrendInsight = engine.refine_loop(
            prompt=compound_prompt,
            initial_schema=TrendInsight,
            criteria="명확하고 구체적인 인사이트 제공, 실행 가능한 권고안 포함, 중복 없는 핵심 요약",
            max_iterations=1,  # 속도를 위해 1회 리파인만 시도
            model=writer_model,
        )

        markdown = f"""
### 트렌드 요약
{insight.summary}

### 주요 발견사항
{chr(10).join([f"- {item}" for item in insight.key_findings])}

### 실행 권고안
{chr(10).join([f"- {item}" for item in insight.recommendations])}

### 키워드
{", ".join(insight.keywords)}

---
*영향력 점수: {insight.impact_score}/10*
"""
        logger.info(f"Trend summarization completed with impact score: {insight.impact_score}")
        return markdown.strip()

    except Exception as e:
        logger.error(f"Error in LLM summarization, falling back to simple summary: {str(e)}")

        # Fallback logic (Keep existing fallback)
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


# ============================================================================
# Simple RAG + Guardrails (Python parity)
# ============================================================================

def _retrieve_relevant_items_keyword(
    query: str,
    items: List[Dict[str, Any]],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Keyword-overlap scoring to pick top-k relevant items (폴백)."""
    tokens = [t for t in _tokenize(query) if len(t) > 1]
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for it in items:
        text = f"{it.get('title','')} {it.get('description','')}".lower()
        score = sum(1 for tok in tokens if tok in text)
        scored.append((score, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[: max(1, top_k)]]


def retrieve_relevant_items(
    query: str,
    items: List[Dict[str, Any]],
    top_k: int = 10,
    use_graph: bool = True,
) -> List[Dict[str, Any]]:
    """
    설정 기반 RAG + 키워드 폴백.

    RAGSystem 공통 모듈을 사용하여 Pinecone 등 벡터 스토어와 연동합니다.
    설정에 없거나 실패 시 키워드 매칭으로 폴백합니다.
    """
    # 1. Initialize RAG system for this agent
    rag = RAGSystem("news_trend_agent")

    # 2. Check if RAG is enabled in config
    if not rag.is_enabled():
        return _retrieve_relevant_items_keyword(query, items, top_k)

    try:
        # 3. Index documents (if not already indexed - naive approach indexes every time)
        # Optimization: In production, check if exists using content hash IDs or similar
        documents = []
        for it in items:
            text = f"{it.get('title','')} {it.get('description','')} {it.get('content','')}"
            documents.append(text)

        if not documents:
            return []

        rag.index_documents(documents, items)

        # 4. Retrieve (GraphRAG simulation optional)
        results = rag.retrieve(query, top_k, use_graph=use_graph)

        if not results:
            return _retrieve_relevant_items_keyword(query, items, top_k)

        return results

    except Exception as e:
        logger.warning(f"RAG retrieve failed, falling back to keyword scoring: {e}")
        return _retrieve_relevant_items_keyword(query, items, top_k)


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[^0-9A-Za-z가-힣]+", (text or "").lower()) if t]


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s-]?\d{3,4}[\s-]?\d{4}\b")
_UNSAFE_KEYWORDS = {"violence", "hate", "terror", "extremist", "weapon"}


def redact_pii(text: str) -> Dict[str, Any]:
    """Redact common PII patterns (emails, phone numbers)."""
    if not text:
        return {"redacted": text, "pii_found": False}
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    pii = redacted != text
    redacted2 = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    pii = pii or (redacted2 != redacted)
    return {"redacted": redacted2, "pii_found": pii}


def check_safety(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    cats = [kw for kw in _UNSAFE_KEYWORDS if kw in lowered]
    return {"unsafe": len(cats) > 0, "categories": cats}
