"""
LLM 기반 분석 도구

기능:
- 감성 분석
- 키워드 추출
- 토픽 클러스터링
- 인사이트 생성
- Self-Refine 루프
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .llm_client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """분석 결과 데이터 클래스."""

    sentiment: Dict[str, Any] = field(default_factory=dict)
    keywords: List[Dict[str, Any]] = field(default_factory=list)
    topics: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sentiment": self.sentiment,
            "keywords": self.keywords,
            "topics": self.topics,
            "summary": self.summary,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "model": self.model,
        }


# =============================================================================
# Sentiment Analysis
# =============================================================================


def analyze_sentiment_llm(
    texts: List[str], language: str = "ko", detailed: bool = True
) -> Dict[str, Any]:
    """
    LLM 기반 감성 분석.

    Args:
        texts: 분석할 텍스트 리스트
        language: 언어 코드
        detailed: 상세 분석 여부

    Returns:
        감성 분석 결과
    """
    if not texts:
        return {
            "overall": "neutral",
            "positive_pct": 0.0,
            "neutral_pct": 100.0,
            "negative_pct": 0.0,
            "distribution": {"positive": 0, "neutral": 0, "negative": 0},
        }

    # Sample texts if too many
    sample_texts = texts[:50] if len(texts) > 50 else texts
    combined_text = "\n---\n".join(sample_texts[:20])

    prompt = f"""Analyze the sentiment of the following texts and provide a structured analysis.

Texts to analyze:
{combined_text}

Provide your analysis in the following JSON format:
{{
    "overall": "positive" | "neutral" | "negative",
    "positive_pct": <percentage 0-100>,
    "neutral_pct": <percentage 0-100>,
    "negative_pct": <percentage 0-100>,
    "confidence": <0.0-1.0>,
    "key_emotions": ["emotion1", "emotion2", ...],
    "sentiment_drivers": [
        {{"topic": "topic", "sentiment": "positive|neutral|negative", "reason": "why"}}
    ],
    "summary": "Overall sentiment summary in {'Korean' if language == 'ko' else 'English'}"
}}

Analyze carefully considering context, sarcasm, and nuance."""

    try:
        client = get_llm_client()
        response = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert sentiment analyst. Provide accurate, nuanced sentiment analysis.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        # Ensure required fields
        result = {
            "overall": response.get("overall", "neutral"),
            "positive_pct": response.get("positive_pct", 33.3),
            "neutral_pct": response.get("neutral_pct", 33.3),
            "negative_pct": response.get("negative_pct", 33.3),
            "confidence": response.get("confidence", 0.7),
            "key_emotions": response.get("key_emotions", []),
            "sentiment_drivers": response.get("sentiment_drivers", []),
            "summary": response.get("summary", ""),
            "model": "llm",
            "sample_size": len(sample_texts),
        }

        logger.info(
            f"Sentiment analysis complete: {result['overall']} ({result['confidence']:.2f})"
        )
        return result

    except Exception as e:
        logger.error(f"LLM sentiment analysis failed: {e}")
        # Fallback to simple analysis
        return _fallback_sentiment_analysis(texts)


def _fallback_sentiment_analysis(texts: List[str]) -> Dict[str, Any]:
    """폴백 감성 분석 (키워드 기반)."""
    positive_words = {"좋", "great", "love", "추천", "만족", "excellent", "amazing", "최고"}
    negative_words = {"나쁨", "bad", "hate", "불만", "싫", "terrible", "worst", "문제"}

    pos = neg = neu = 0
    for text in texts:
        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        if pos_count > neg_count:
            pos += 1
        elif neg_count > pos_count:
            neg += 1
        else:
            neu += 1

    total = max(1, pos + neg + neu)
    return {
        "overall": "positive" if pos > neg else "negative" if neg > pos else "neutral",
        "positive_pct": (pos / total) * 100,
        "neutral_pct": (neu / total) * 100,
        "negative_pct": (neg / total) * 100,
        "confidence": 0.5,
        "model": "keyword_fallback",
    }


# =============================================================================
# Keyword Extraction
# =============================================================================


def extract_keywords_llm(
    texts: List[str], max_keywords: int = 20, language: str = "ko"
) -> List[Dict[str, Any]]:
    """
    LLM 기반 키워드 추출.

    Args:
        texts: 텍스트 리스트
        max_keywords: 최대 키워드 수
        language: 언어 코드

    Returns:
        키워드 리스트 [{"keyword": str, "score": float, "category": str}]
    """
    if not texts:
        return []

    combined_text = "\n".join(texts[:30])

    prompt = f"""Extract the most important and relevant keywords from the following texts.

Texts:
{combined_text}

Extract up to {max_keywords} keywords and provide in this JSON format:
{{
    "keywords": [
        {{
            "keyword": "keyword text",
            "score": <relevance score 0.0-1.0>,
            "category": "topic category",
            "frequency": <estimated frequency>
        }}
    ]
}}

Focus on:
- Key topics and themes
- Named entities (brands, products, people)
- Trending terms
- Domain-specific terminology

Sort by relevance score descending."""

    try:
        client = get_llm_client()
        response = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting meaningful keywords from text.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        keywords = response.get("keywords", [])
        logger.info(f"Extracted {len(keywords)} keywords")
        return keywords[:max_keywords]

    except Exception as e:
        logger.error(f"LLM keyword extraction failed: {e}")
        return _fallback_keyword_extraction(texts, max_keywords)


def _fallback_keyword_extraction(texts: List[str], max_keywords: int) -> List[Dict[str, Any]]:
    """폴백 키워드 추출 (빈도 기반)."""
    from collections import Counter
    import re

    # Simple tokenization
    words = []
    for text in texts:
        tokens = re.findall(r"\b\w+\b", text.lower())
        words.extend([t for t in tokens if len(t) > 2])

    # Count and filter
    word_counts = Counter(words)

    # Remove common stopwords
    stopwords = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "and",
        "or",
        "but",
        "이",
        "그",
        "저",
        "것",
        "수",
    }
    for sw in stopwords:
        word_counts.pop(sw, None)

    # Format result
    keywords = []
    for word, count in word_counts.most_common(max_keywords):
        keywords.append(
            {
                "keyword": word,
                "score": min(count / 10, 1.0),
                "frequency": count,
                "category": "general",
            }
        )

    return keywords


# =============================================================================
# Topic Clustering
# =============================================================================


def cluster_topics_llm(
    texts: List[str], num_topics: int = 5, language: str = "ko"
) -> List[Dict[str, Any]]:
    """
    LLM 기반 토픽 클러스터링.

    Args:
        texts: 텍스트 리스트
        num_topics: 추출할 토픽 수
        language: 언어 코드

    Returns:
        토픽 리스트 [{"topic": str, "description": str, "keywords": [...], "count": int}]
    """
    if not texts:
        return []

    combined_text = "\n---\n".join(texts[:40])

    prompt = f"""Analyze the following texts and identify {num_topics} main topics/themes.

Texts:
{combined_text}

Provide your analysis in this JSON format:
{{
    "topics": [
        {{
            "topic": "Topic name",
            "description": "Brief description of this topic",
            "keywords": ["related", "keywords"],
            "sentiment": "positive|neutral|negative",
            "importance": <0.0-1.0>,
            "example_texts": ["short example 1", "short example 2"]
        }}
    ]
}}

Sort topics by importance (most important first).
Provide topic names in {'Korean' if language == 'ko' else 'English'}."""

    try:
        client = get_llm_client()
        response = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at identifying and clustering topics in text data.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        topics = response.get("topics", [])
        logger.info(f"Identified {len(topics)} topics")
        return topics

    except Exception as e:
        logger.error(f"LLM topic clustering failed: {e}")
        return []


# =============================================================================
# Insight Generation
# =============================================================================


def generate_insights_llm(
    query: str,
    texts: List[str],
    sentiment: Dict[str, Any],
    keywords: List[Dict[str, Any]],
    topics: List[Dict[str, Any]],
    language: str = "ko",
    self_refine: bool = True,
) -> Dict[str, Any]:
    """
    LLM 기반 인사이트 생성.

    Args:
        query: 원본 쿼리
        texts: 분석된 텍스트
        sentiment: 감성 분석 결과
        keywords: 키워드 추출 결과
        topics: 토픽 클러스터링 결과
        language: 출력 언어
        self_refine: Self-Refine 루프 사용 여부

    Returns:
        인사이트 결과
    """
    # Prepare context
    context = {
        "query": query,
        "sample_texts": texts[:10],
        "sentiment": sentiment,
        "top_keywords": keywords[:10],
        "main_topics": topics[:5],
    }

    lang_instruction = "한국어로 작성하세요." if language == "ko" else "Write in English."

    prompt = f"""Based on the following analysis of "{query}", generate actionable insights.

Analysis Context:
{json.dumps(context, ensure_ascii=False, indent=2)}

Generate insights in this JSON format:
{{
    "summary": "Executive summary (2-3 sentences)",
    "key_findings": [
        "Finding 1",
        "Finding 2",
        ...
    ],
    "insights": [
        {{
            "title": "Insight title",
            "description": "Detailed description",
            "evidence": "Supporting evidence from data",
            "impact": "high|medium|low"
        }}
    ],
    "recommendations": [
        {{
            "action": "Specific action to take",
            "rationale": "Why this action",
            "priority": "high|medium|low",
            "timeline": "immediate|short-term|long-term"
        }}
    ],
    "risks": ["Risk 1", "Risk 2"],
    "opportunities": ["Opportunity 1", "Opportunity 2"]
}}

{lang_instruction}
Focus on actionable, specific, and evidence-based insights."""

    try:
        client = get_llm_client()

        # Initial generation
        response = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior trend analyst providing actionable business insights.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )

        # Self-Refine loop
        if self_refine:
            response = _self_refine_insights(response, query, language)

        logger.info(f"Generated insights with {len(response.get('insights', []))} items")
        return response

    except Exception as e:
        logger.error(f"LLM insight generation failed: {e}")
        return {
            "summary": f"Analysis of {query}",
            "key_findings": [],
            "insights": [],
            "recommendations": [],
            "risks": [],
            "opportunities": [],
        }


def _self_refine_insights(
    initial_response: Dict[str, Any], query: str, language: str
) -> Dict[str, Any]:
    """
    Self-Refine 루프로 인사이트 품질 개선.

    1. 평가 프롬프트로 품질 체크
    2. 개선점 식별
    3. 수정본 생성
    """
    client = get_llm_client()

    # Evaluation prompt
    eval_prompt = f"""Evaluate the following insights for "{query}":

{json.dumps(initial_response, ensure_ascii=False, indent=2)}

Evaluate on these criteria and provide improvement suggestions:
{{
    "scores": {{
        "specificity": <0-10>,
        "actionability": <0-10>,
        "evidence_based": <0-10>,
        "clarity": <0-10>
    }},
    "improvements_needed": [
        "Specific improvement 1",
        "Specific improvement 2"
    ],
    "overall_quality": "excellent|good|needs_improvement"
}}"""

    try:
        evaluation = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are a quality assurance expert for business insights.",
                },
                {"role": "user", "content": eval_prompt},
            ],
            temperature=0.3,
        )

        # If quality is good, return original
        if evaluation.get("overall_quality") == "excellent":
            return initial_response

        # Generate refined version
        improvements = evaluation.get("improvements_needed", [])
        if not improvements:
            return initial_response

        refine_prompt = f"""Improve the following insights based on this feedback:

Original insights:
{json.dumps(initial_response, ensure_ascii=False, indent=2)}

Improvements needed:
{json.dumps(improvements, ensure_ascii=False)}

Generate an improved version maintaining the same JSON structure.
{'한국어로 작성하세요.' if language == 'ko' else 'Write in English.'}"""

        refined = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": "You are refining business insights for higher quality.",
                },
                {"role": "user", "content": refine_prompt},
            ],
            temperature=0.4,
        )

        logger.info("Self-refined insights")
        return refined

    except Exception as e:
        logger.warning(f"Self-refine failed: {e}. Using initial response.")
        return initial_response


# =============================================================================
# Combined Analysis
# =============================================================================


def analyze_texts_comprehensive(
    query: str, texts: List[str], language: str = "ko", include_recommendations: bool = True
) -> AnalysisResult:
    """
    종합 텍스트 분석.

    감성, 키워드, 토픽, 인사이트를 한 번에 분석.

    Args:
        query: 검색 쿼리
        texts: 분석할 텍스트 리스트
        language: 출력 언어
        include_recommendations: 권고사항 포함 여부

    Returns:
        AnalysisResult 객체
    """
    logger.info(f"Starting comprehensive analysis for '{query}' with {len(texts)} texts")

    # Run analyses
    sentiment = analyze_sentiment_llm(texts, language)
    keywords = extract_keywords_llm(texts, language=language)
    topics = cluster_topics_llm(texts, language=language)

    insights_data = {}
    if include_recommendations:
        insights_data = generate_insights_llm(query, texts, sentiment, keywords, topics, language)

    # Build result
    result = AnalysisResult(
        sentiment=sentiment,
        keywords=keywords,
        topics=topics,
        summary=insights_data.get("summary", ""),
        insights=insights_data.get("key_findings", []),
        recommendations=[rec.get("action", "") for rec in insights_data.get("recommendations", [])],
        confidence=sentiment.get("confidence", 0.7),
        model="llm_comprehensive",
    )

    logger.info("Comprehensive analysis complete")
    return result
