"""
뉴스 트렌드 에이전트를 위한 도구

Phase 3 유틸리티 통합: 재시도, 캐싱, 로깅
"""
# mypy: ignore-errors
import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
import re

# Phase 3 utilities
from src.infrastructure.retry import backoff_retry
from src.infrastructure.cache import cached
from src.core.config import get_config_manager
from src.integrations.llm import get_llm_client
from src.integrations.retrieval.vectorstore_pinecone import PineconeVectorStore
from src.integrations.mcp.news_collect import search_news_via_mcp

# LangChain for LLM integration (뉴스 에이전트는 LangChain 기반 요약 체인을 유지)
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

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
    news_items = search_news_via_mcp(
        query=query,
        time_window=time_window,
        language=language,
        max_results=max_results,
    )

    # MCP 결과가 없으면 샘플 데이터로 폴백
    if not news_items:
        logger.warning("No news items from MCP, using sample data")
        news_items = _get_sample_news(query, time_window, language)

    logger.info(f"News search completed: total_results={len(news_items)}")
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
    from src.integrations.llm import get_llm_client

    client = get_llm_client(agent_name="news_trend_agent")

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

    result = client.chat_json(
        messages=[
            {"role": "system", "content": "You are a sentiment analysis expert. Analyze Korean and English text accurately."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
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
    """TF-IDF 기반 키워드 추출 (sklearn 없이 경량 구현)."""
    import math

    # Prepare tokenized documents
    documents: List[List[str]] = []
    doc_freq: Dict[str, int] = {}

    # Korean + English stop words
    stop_words = {
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
        "too", "very", "just", "also", "now", "said", "says",
    }

    for item in items:
        text = f"{item.get('title', '')} {item.get('description', '')} {item.get('content', '')}"
        tokens = re.findall(r"[가-힣a-zA-Z]{2,}", text.lower())
        tokens = [t for t in tokens if t not in stop_words]
        if not tokens:
            continue
        documents.append(tokens)

        # Update document frequency (per unique token in this document)
        for token in set(tokens):
            doc_freq[token] = doc_freq.get(token, 0) + 1

    if not documents:
        return {"top_keywords": [], "total_unique_keywords": 0}

    num_docs = len(documents)

    # Compute TF-IDF scores
    tfidf_scores: Dict[str, float] = {}
    for tokens in documents:
        doc_len = len(tokens)
        counts: Dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1

        for token, cnt in counts.items():
            tf = cnt / doc_len
            df = doc_freq.get(token, 1)
            idf = math.log(num_docs / df) + 1.0
            tfidf_scores[token] = tfidf_scores.get(token, 0.0) + tf * idf

    # Sort by TF-IDF score
    sorted_keywords = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)

    top_keywords = [
        {
            "keyword": kw,
            "score": round(score, 4),
            "count": doc_freq.get(kw, 0),
        }
        for kw, score in sorted_keywords[:20]
        if score > 0
    ]

    return {
        "top_keywords": top_keywords,
        "total_unique_keywords": len(tfidf_scores),
        "method": "tfidf",
        "ngram_range": "1-1",
    }


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
            else os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-5.1")
        )
        return AzureChatOpenAI(
            deployment_name=deployment_name,
            temperature=0.7,
        )
    elif provider == "openai":
        model = model_name or os.getenv("OPENAI_MODEL_NAME", "gpt-5.1")
        return ChatOpenAI(
            model=model,
            temperature=0.7,
        )
    elif provider == "anthropic":
        model = model_name or os.getenv("ANTHROPIC_MODEL_NAME", "claude-3-opus-20240229")
        return ChatAnthropic(
            model=model,
            temperature=0.7,
            max_tokens=1000,
        )
    elif provider == "google":
        model = model_name or os.getenv("GOOGLE_MODEL_NAME", "gemini-pro")
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0.7,
            max_tokens=1000,
        )
    else:
        # Fallback to Azure OpenAI
        logger.warning(f"Unknown LLM provider '{provider}', falling back to Azure OpenAI")
        deployment_name = os.getenv("OPENAI_DEPLOYMENT_NAME", "gpt-5.1")
        return AzureChatOpenAI(
            deployment_name=deployment_name,
            temperature=0.7,
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
    logger.info(f"Starting trend summarization: query={query}, item_count={len(normalized_items)}")

    sentiment = analysis.get("sentiment", {})
    keywords = analysis.get("keywords", {}).get("top_keywords", [])

    # Extract top 5 news headlines
    top_headlines = [item.get("title", "") for item in normalized_items[:5]]

    # Build context for LLM
    keywords_str = ", ".join([kw["keyword"] for kw in keywords[:10]])
    headlines_str = "\n".join([f"- {headline}" for headline in top_headlines])

    # Import prompts from prompts.py for better management
    try:
        from src.agents.news_trend.prompts import get_system_prompt
        system_prompt_text = get_system_prompt()
    except ImportError:
        logger.warning("Failed to import prompts.py, using default prompt")
        system_prompt_text = """당신은 소비자 트렌드 분석 전문가입니다.
주어진 뉴스 데이터를 분석하여 마케팅 및 상품 기획팀이 활용할 수 있는 핵심 인사이트를 제공하세요.

응답 형식:
1. 전반적인 트렌드 요약 (2-3문장)
2. 주요 발견사항 (3-5개 bullet points)
3. 실행 가능한 권고안 (3-5개 bullet points)

명확하고 실용적인 분석을 제공하세요."""

    # Create prompt using LangChain ChatPromptTemplate (official pattern)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt_text),
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

        logger.info(f"Trend summarization completed: summary_length={len(summary)}")
        return summary

    except Exception as e:
        logger.error(f"Error in LLM summarization, falling back to simple summary: {str(e)}")

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
) -> List[Dict[str, Any]]:
    """
    설정 기반 RAG + 키워드 폴백.

    - config.default.yaml 의 agents.news_trend_agent.vector_store.type 이 `pinecone` 이고
      PINECONE_API_KEY 가 설정되어 있으면 Pinecone + 임베딩 기반 검색을 사용
    - 그렇지 않으면 기존 키워드 오버랩 스코어링으로 폴백
    """
    cfg = get_config_manager()
    agent_cfg = cfg.get_agent_config("news_trend_agent")

    vs_cfg: Dict[str, Any] = agent_cfg.vector_store if agent_cfg and agent_cfg.vector_store else {}
    use_pinecone = vs_cfg.get("type") == "pinecone"

    if not use_pinecone:
        return _retrieve_relevant_items_keyword(query, items, top_k)

    try:
        index_name = vs_cfg.get("index_name", "news-trend-index")
        vector_store = PineconeVectorStore(index_name=index_name)

        llm_client = get_llm_client(agent_name="news_trend_agent")

        # Build corpus
        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for idx, it in enumerate(items):
            ids.append(str(idx))
            text = f"{it.get('title','')} {it.get('description','')} {it.get('content','')}"
            texts.append(text)
            metadatas.append(it)

        if not texts:
            return []

        # Upsert into vector store
        vectors = llm_client.get_embeddings_batch(texts)
        vector_store.upsert(ids, vectors, metadatas)

        # Query
        query_vector = llm_client.get_embedding(query)
        matches = vector_store.query(query_vector, top_k=top_k)

        results: List[Dict[str, Any]] = []
        for m in matches:
            meta = m.get("metadata") or {}
            if isinstance(meta, dict):
                results.append(meta)

        if not results:
            return _retrieve_relevant_items_keyword(query, items, top_k)

        return results

    except Exception as e:
        logger.warning(f"Pinecone RAG retrieve failed, falling back to keyword scoring: {e}")
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
