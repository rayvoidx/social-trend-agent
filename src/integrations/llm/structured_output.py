"""
구조화된 출력 스키마 및 Self-Refine 루프

Pydantic 모델을 사용하여 LLM 출력을 검증하고,
Self-Refine 패턴으로 품질을 향상시킵니다.
"""
from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .llm_client import get_llm_client

logger = logging.getLogger(__name__)


# =============================================================================
# Output Schemas
# =============================================================================

class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ImpactLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Timeline(str, Enum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short-term"
    LONG_TERM = "long-term"


class SentimentDriver(BaseModel):
    """감성 드라이버 스키마."""
    topic: str = Field(..., description="주제")
    sentiment: SentimentType = Field(..., description="감성")
    reason: str = Field(..., description="이유")


class SentimentAnalysis(BaseModel):
    """감성 분석 출력 스키마."""
    overall: SentimentType = Field(..., description="전체 감성")
    positive_pct: float = Field(..., ge=0, le=100, description="긍정 비율")
    neutral_pct: float = Field(..., ge=0, le=100, description="중립 비율")
    negative_pct: float = Field(..., ge=0, le=100, description="부정 비율")
    confidence: float = Field(..., ge=0, le=1, description="신뢰도")
    key_emotions: List[str] = Field(default_factory=list, description="핵심 감정")
    sentiment_drivers: List[SentimentDriver] = Field(default_factory=list)
    summary: str = Field(..., description="요약")

    @validator('positive_pct', 'neutral_pct', 'negative_pct')
    def validate_percentage(cls, v):
        return round(v, 1)


class Keyword(BaseModel):
    """키워드 스키마."""
    keyword: str = Field(..., description="키워드")
    score: float = Field(..., ge=0, le=1, description="관련성 점수")
    category: str = Field(default="general", description="카테고리")
    frequency: int = Field(default=1, ge=0, description="빈도")


class KeywordExtraction(BaseModel):
    """키워드 추출 출력 스키마."""
    keywords: List[Keyword] = Field(..., description="키워드 리스트")


class Topic(BaseModel):
    """토픽 스키마."""
    topic: str = Field(..., description="토픽 이름")
    description: str = Field(..., description="토픽 설명")
    keywords: List[str] = Field(default_factory=list, description="관련 키워드")
    sentiment: SentimentType = Field(default=SentimentType.NEUTRAL)
    importance: float = Field(..., ge=0, le=1, description="중요도")
    example_texts: List[str] = Field(default_factory=list, description="예시")


class TopicClustering(BaseModel):
    """토픽 클러스터링 출력 스키마."""
    topics: List[Topic] = Field(..., description="토픽 리스트")


class Insight(BaseModel):
    """인사이트 스키마."""
    title: str = Field(..., description="인사이트 제목")
    description: str = Field(..., description="상세 설명")
    evidence: str = Field(..., description="근거")
    impact: ImpactLevel = Field(..., description="영향도")


class Recommendation(BaseModel):
    """권고사항 스키마."""
    action: str = Field(..., description="실행 항목")
    rationale: str = Field(..., description="근거")
    priority: Priority = Field(..., description="우선순위")
    timeline: Timeline = Field(..., description="실행 시점")


class InsightGeneration(BaseModel):
    """인사이트 생성 출력 스키마."""
    summary: str = Field(..., description="요약")
    key_findings: List[str] = Field(..., description="핵심 발견사항")
    insights: List[Insight] = Field(..., description="인사이트")
    recommendations: List[Recommendation] = Field(..., description="권고사항")
    risks: List[str] = Field(default_factory=list, description="리스크")
    opportunities: List[str] = Field(default_factory=list, description="기회")


class MissionDraft(BaseModel):
    """미션 초안 스키마."""
    title: str = Field(..., description="미션 제목")
    objective: str = Field(..., description="목표")
    target_audience: str = Field(..., description="타겟 오디언스")
    content_guidelines: List[str] = Field(..., description="콘텐츠 가이드라인")
    kpis: List[Dict[str, Any]] = Field(..., description="KPI")
    budget_range: str = Field(..., description="예산 범위")
    timeline: str = Field(..., description="일정")


# =============================================================================
# Self-Refine Implementation
# =============================================================================

class QualityScore(BaseModel):
    """품질 평가 점수."""
    specificity: int = Field(..., ge=0, le=10, description="구체성")
    actionability: int = Field(..., ge=0, le=10, description="실행가능성")
    evidence_based: int = Field(..., ge=0, le=10, description="근거기반")
    clarity: int = Field(..., ge=0, le=10, description="명확성")
    completeness: int = Field(..., ge=0, le=10, description="완전성")

    @property
    def total(self) -> float:
        return (self.specificity + self.actionability +
                self.evidence_based + self.clarity + self.completeness) / 5


class QualityEvaluation(BaseModel):
    """품질 평가 결과."""
    scores: QualityScore
    improvements_needed: List[str] = Field(default_factory=list)
    overall_quality: str = Field(..., description="excellent|good|needs_improvement")


def self_refine_output(
    initial_output: Dict[str, Any],
    output_schema: type[BaseModel],
    context: str,
    language: str = "ko",
    max_iterations: int = 2
) -> Dict[str, Any]:
    """
    Self-Refine 루프로 출력 품질 개선.

    Args:
        initial_output: 초기 LLM 출력
        output_schema: Pydantic 스키마
        context: 원본 컨텍스트
        language: 출력 언어
        max_iterations: 최대 반복 횟수

    Returns:
        개선된 출력
    """
    client = get_llm_client()
    current_output = initial_output

    for iteration in range(max_iterations):
        # Step 1: Evaluate quality
        evaluation = _evaluate_output_quality(current_output, context)

        logger.info(
            f"Iteration {iteration + 1}: Quality score = {evaluation.scores.total:.1f}/10, "
            f"Status = {evaluation.overall_quality}"
        )

        # Step 2: Check if good enough
        if evaluation.overall_quality == "excellent":
            logger.info("Output quality is excellent. Stopping refinement.")
            break

        if not evaluation.improvements_needed:
            logger.info("No improvements needed. Stopping refinement.")
            break

        # Step 3: Refine based on feedback
        current_output = _refine_output(
            current_output,
            evaluation.improvements_needed,
            output_schema,
            language
        )

    # Validate against schema
    try:
        validated = output_schema(**current_output)
        return validated.dict()
    except Exception as e:
        logger.warning(f"Schema validation failed: {e}. Returning raw output.")
        return current_output


def _evaluate_output_quality(
    output: Dict[str, Any],
    context: str
) -> QualityEvaluation:
    """출력 품질 평가."""
    client = get_llm_client()

    eval_prompt = f"""Evaluate the quality of this output:

Output:
{json.dumps(output, ensure_ascii=False, indent=2)}

Context: {context[:500]}

Provide evaluation in this JSON format:
{{
    "scores": {{
        "specificity": <0-10>,
        "actionability": <0-10>,
        "evidence_based": <0-10>,
        "clarity": <0-10>,
        "completeness": <0-10>
    }},
    "improvements_needed": [
        "Specific improvement 1",
        "Specific improvement 2"
    ],
    "overall_quality": "excellent" | "good" | "needs_improvement"
}}

Score 8+ for excellent, 6-7 for good, below 6 needs improvement."""

    try:
        response = client.chat_json(
            messages=[
                {"role": "system", "content": "You are a quality assurance expert."},
                {"role": "user", "content": eval_prompt}
            ],
            temperature=0.2,
        )

        return QualityEvaluation(**response)

    except Exception as e:
        logger.error(f"Quality evaluation failed: {e}")
        return QualityEvaluation(
            scores=QualityScore(
                specificity=7, actionability=7,
                evidence_based=7, clarity=7, completeness=7
            ),
            improvements_needed=[],
            overall_quality="good"
        )


def _refine_output(
    output: Dict[str, Any],
    improvements: List[str],
    schema: type[BaseModel],
    language: str
) -> Dict[str, Any]:
    """개선 피드백 기반 출력 수정."""
    client = get_llm_client()

    # Get schema as JSON
    schema_json = schema.schema_json(indent=2)

    refine_prompt = f"""Improve this output based on the feedback:

Current output:
{json.dumps(output, ensure_ascii=False, indent=2)}

Improvements needed:
{json.dumps(improvements, ensure_ascii=False)}

Output must conform to this schema:
{schema_json}

{'한국어로 작성하세요.' if language == 'ko' else 'Write in English.'}
Provide the improved output as valid JSON."""

    try:
        refined = client.chat_json(
            messages=[
                {"role": "system", "content": "You are improving output quality."},
                {"role": "user", "content": refine_prompt}
            ],
            temperature=0.3,
        )

        logger.debug("Output refined successfully")
        return refined

    except Exception as e:
        logger.error(f"Refinement failed: {e}")
        return output


# =============================================================================
# Structured Analysis Functions
# =============================================================================

def analyze_with_schema(
    texts: List[str],
    query: str,
    language: str = "ko"
) -> Dict[str, Any]:
    """
    구조화된 스키마로 종합 분석.

    Args:
        texts: 분석할 텍스트
        query: 검색 쿼리
        language: 출력 언어

    Returns:
        검증된 분석 결과
    """
    client = get_llm_client()
    combined_text = "\n---\n".join(texts[:30])

    # Get schemas
    sentiment_schema = SentimentAnalysis.schema()
    keyword_schema = KeywordExtraction.schema()
    topic_schema = TopicClustering.schema()

    prompt = f"""Analyze the following texts about "{query}".

Texts:
{combined_text}

Provide comprehensive analysis in this JSON format:
{{
    "sentiment": {json.dumps(sentiment_schema['properties'], indent=2)},
    "keywords": {json.dumps(keyword_schema['properties'], indent=2)},
    "topics": {json.dumps(topic_schema['properties'], indent=2)}
}}

{'한국어로 작성하세요.' if language == 'ko' else 'Write in English.'}"""

    try:
        response = client.chat_json(
            messages=[
                {"role": "system", "content": "You are an expert analyst providing structured analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
        )

        # Refine each section
        if "sentiment" in response:
            response["sentiment"] = self_refine_output(
                response["sentiment"],
                SentimentAnalysis,
                query,
                language,
                max_iterations=1
            )

        return response

    except Exception as e:
        logger.error(f"Structured analysis failed: {e}")
        return {}


def generate_mission_draft(
    insight: Dict[str, Any],
    language: str = "ko"
) -> Dict[str, Any]:
    """
    인사이트에서 미션 초안 생성.

    Args:
        insight: 인사이트 데이터
        language: 출력 언어

    Returns:
        미션 초안
    """
    client = get_llm_client()
    schema = MissionDraft.schema()

    prompt = f"""Based on this insight, generate a marketing mission draft:

Insight:
{json.dumps(insight, ensure_ascii=False, indent=2)}

Generate a mission in this JSON format:
{json.dumps(schema['properties'], indent=2)}

{'한국어로 작성하세요.' if language == 'ko' else 'Write in English.'}
Focus on actionable, measurable objectives."""

    try:
        response = client.chat_json(
            messages=[
                {"role": "system", "content": "You are a marketing strategist creating campaign missions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
        )

        # Refine
        refined = self_refine_output(
            response,
            MissionDraft,
            f"Mission for insight: {insight.get('summary', '')}",
            language
        )

        return refined

    except Exception as e:
        logger.error(f"Mission draft generation failed: {e}")
        return {}
