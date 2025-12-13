"""
모든 에이전트를 위한 공통 상태 스키마
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """LangGraph 패턴을 따르는 모든 에이전트의 기본 상태"""

    # 입력
    query: str = Field(..., description="사용자 쿼리 또는 검색어")
    time_window: Optional[str] = Field(None, description="시간 범위 (예: last_24h, 7d, 30d)")

    # 데이터 파이프라인
    raw_items: List[Dict[str, Any]] = Field(default_factory=list, description="원시 수집 항목")
    normalized: List[Dict[str, Any]] = Field(default_factory=list, description="정규화/정제된 항목")

    # 분석 결과
    analysis: Dict[str, Any] = Field(default_factory=dict, description="분석 결과 (감성, 키워드 등)")

    # 2025: Orchestrator/Planner outputs (optional)
    orchestrator: Optional[Dict[str, Any]] = Field(
        default=None,
        description="오케스트레이터(3-gear)에서 생성된 routing/plan 정보",
    )
    plan: Dict[str, Any] = Field(
        default_factory=dict,
        description="에이전트/플래너가 생성한 실행 계획(툴 사용 계획 포함)",
    )
    plan_execution: Dict[str, Any] = Field(
        default_factory=dict,
        description="실행 중 plan 상태(완료 step, 현재 step 등). 동적 계획 실행에 사용",
    )

    # 출력
    report_md: Optional[str] = Field(None, description="최종 마크다운 리포트")

    # 메트릭
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="품질 메트릭 (커버리지, 사실성, 실행 가능성)"
    )

    # 메타데이터
    run_id: Optional[str] = Field(None, description="고유 실행 식별자")
    error: Optional[str] = Field(None, description="실패 시 에러 메시지")


class NewsAgentState(AgentState):
    """뉴스 트렌드 에이전트를 위한 확장 상태"""
    language: Optional[str] = Field("ko", description="언어 코드 (ko, en)")
    max_results: int = Field(20, description="최대 결과 수")


class ViralAgentState(AgentState):
    """바이럴 비디오 에이전트를 위한 확장 상태"""
    market: str = Field("KR", description="시장 코드 (KR, US 등)")
    platforms: List[str] = Field(default_factory=lambda: ["youtube"], description="분석할 플랫폼")
    spike_threshold: float = Field(2.0, description="급증 탐지를 위한 Z-score 임계값")


class SocialTrendAgentState(AgentState):
    """소셜 트렌드 에이전트를 위한 확장 상태"""
    platforms: List[str] = Field(
        default_factory=lambda: ["x", "instagram", "naver_blog"],
        description="수집할 소셜 플랫폼"
    )
    hashtags: List[str] = Field(default_factory=list, description="추적할 해시태그")
    influencers: List[Dict[str, Any]] = Field(default_factory=list, description="발견된 인플루언서")
    trending_topics: List[Dict[str, Any]] = Field(default_factory=list, description="트렌딩 토픽")
    engagement_stats: Dict[str, Any] = Field(default_factory=dict, description="플랫폼별 참여도 통계")
    language: str = Field("ko", description="언어 코드")
    max_results_per_platform: int = Field(50, description="플랫폼당 최대 결과 수")
    include_rss: bool = Field(True, description="RSS 피드 포함 여부")
    rss_feeds: List[str] = Field(default_factory=list, description="RSS 피드 URL 목록")
