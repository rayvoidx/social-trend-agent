"""
Domain Schemas for Structured Output
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class TrendInsight(BaseModel):
    """트렌드 분석 인사이트 스키마"""

    summary: str = Field(description="전반적인 트렌드 요약 (2-3문장)")
    key_findings: List[str] = Field(description="주요 발견사항 (3-5개 bullet points)")
    recommendations: List[str] = Field(description="실행 가능한 권고안 (3-5개 bullet points)")
    impact_score: int = Field(description="트렌드 영향력 점수 (1-10)", ge=1, le=10)
    keywords: List[str] = Field(description="관련 핵심 키워드")


class QualityCheck(BaseModel):
    """콘텐츠 품질 평가 스키마"""

    score: int = Field(description="품질 점수 (1-10)", ge=1, le=10)
    feedback: str = Field(description="개선이 필요한 부분에 대한 피드백")
    is_pass: bool = Field(description="품질 기준 통과 여부 (점수 >= 7)")
    issues: List[str] = Field(default_factory=list, description="발견된 구체적인 문제점들")


class RefinementResult(BaseModel):
    """Self-Refine 결과"""

    original_content: TrendInsight
    refined_content: Optional[TrendInsight] = None
    quality_check: QualityCheck
    iteration_count: int = 0
