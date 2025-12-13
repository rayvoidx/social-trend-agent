"""
Core domain models for missions, creators, rewards and insights.

이 모듈은 에이전트에서 생성하는 인사이트를
미션/크리에이터/보상 도메인과 연결하기 위한 공통 스키마를 제공합니다.

초기 구현은 인메모리 저장소를 대상으로 설계되며,
향후 DB/Redis 백엔드로 확장할 수 있도록 최소한의 추상화를 포함합니다.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from enum import Enum
from typing import Any, Dict, Generic, List, Mapping, Optional, Protocol, Sequence, TypeVar

from pydantic import BaseModel, Field, HttpUrl, PositiveFloat, PositiveInt, model_validator


TModel = TypeVar("TModel", bound=BaseModel)


class MissionStatus(str, Enum):
    """상위 레벨 미션 상태"""

    DRAFT = "draft"
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RewardStatus(str, Enum):
    """보상 지급 상태"""

    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"


class InsightSource(str, Enum):
    """인사이트를 생성한 에이전트/소스 구분"""

    NEWS_TREND = "news_trend_agent"
    VIRAL_VIDEO = "viral_video_agent"
    SOCIAL_TREND = "social_trend_agent"


class CreatorPlatform(str, Enum):
    """크리에이터 주요 플랫폼"""

    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    X = "x"
    NAVER_BLOG = "naver_blog"


class Insight(BaseModel):
    """
    에이전트가 생성한 분석 결과의 도메인 표현.

    - 에이전트 종류, 쿼리, 기간, 감성/키워드 요약, 추천 액션 등을 포함합니다.
    - artifacts 에 저장된 리포트 경로와 run_id 를 함께 보관합니다.
    """

    id: str = Field(..., description="고유 인사이트 ID")
    source: InsightSource = Field(..., description="어떤 에이전트가 생성했는지")
    query: str = Field(..., description="인사이트를 생성한 쿼리/주제")
    time_window: Optional[str] = Field(
        default=None,
        description="에이전트 실행 시 사용한 시간 범위 (예: 24h, 7d, 30d)",
    )
    language: Optional[str] = Field(
        default=None,
        description="분석에 사용된 언어 (예: ko, en)",
    )

    sentiment_summary: Optional[str] = Field(
        default=None,
        description="긍정/중립/부정 비율 등을 한 줄로 요약한 텍스트",
    )
    top_keywords: List[str] = Field(
        default_factory=list,
        description="주요 키워드 텍스트 리스트",
    )
    summary: Optional[str] = Field(
        default=None,
        description="에이전트가 생성한 핵심 요약 텍스트",
    )
    recommended_actions: List[str] = Field(
        default_factory=list,
        description="바로 실행 가능한 액션 아이템들 (문장 단위)",
    )

    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="커버리지/사실성/실행 가능성 등 수치 메트릭",
    )

    run_id: Optional[str] = Field(
        default=None,
        description="에이전트 실행 식별자 (artifacts 파일명 등과 연결)",
    )
    report_path: Optional[str] = Field(
        default=None,
        description="artifacts 에 저장된 마크다운 리포트 경로",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="인사이트 생성 시각",
    )


class Creator(BaseModel):
    """
    캠페인/미션을 수행하는 크리에이터/채널 정보.
    """

    id: str = Field(..., description="크리에이터 고유 ID")
    name: str = Field(..., description="표시용 이름")
    handle: Optional[str] = Field(
        default=None,
        description="플랫폼에서 사용하는 핸들 (예: @channel_name)",
    )

    primary_platform: CreatorPlatform = Field(
        ...,
        description="주요 활동 플랫폼",
    )
    platforms: List[CreatorPlatform] = Field(
        default_factory=list,
        description="활동 중인 플랫폼 리스트",
    )

    category: Optional[str] = Field(
        default=None,
        description="카테고리/니치 (예: beauty, tech, lifestyle)",
    )
    language: Optional[str] = Field(
        default=None,
        description="주로 사용하는 언어 코드 (예: ko, en)",
    )

    followers: Optional[int] = Field(
        default=None,
        ge=0,
        description="주요 플랫폼 팔로워/구독자 수 (대략적인 값)",
    )
    avg_view_per_post: Optional[int] = Field(
        default=None,
        ge=0,
        description="평균 콘텐츠당 조회수 (대략적인 값)",
    )
    avg_engagement_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="평균 참여율 (0~1 사이 비율)",
    )

    external_url: Optional[HttpUrl] = Field(
        default=None,
        description="크리에이터 소개/채널 링크",
    )


class Mission(BaseModel):
    """
    인사이트를 기반으로 실행되는 마케팅 미션/캠페인 단위.
    """

    id: str = Field(..., description="미션 고유 ID")
    title: str = Field(..., min_length=1, description="미션 제목")
    description: str = Field(..., min_length=1, description="미션 상세 설명")

    insight_id: Optional[str] = Field(
        default=None,
        description="이 미션을 촉발한 인사이트 ID",
    )

    target_audience: Optional[str] = Field(
        default=None,
        description="목표 타겟 오디언스 (예: 20-30대, 직장인, 크리에이터 등)",
    )

    platforms: List[CreatorPlatform] = Field(
        default_factory=list,
        description="집행 대상 플랫폼 리스트",
    )

    expected_start: Optional[datetime] = Field(
        default=None,
        description="예상 시작 시각",
    )
    expected_end: Optional[datetime] = Field(
        default=None,
        description="예상 종료 시각",
    )

    status: MissionStatus = Field(
        default=MissionStatus.DRAFT,
        description="미션 현재 상태",
    )

    budget: Optional[PositiveFloat] = Field(
        default=None,
        description="예산 (통화 단위는 상위 레벨에서 관리)",
    )

    kpi_click_through_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="목표 클릭률 (0~1 비율)",
    )
    kpi_conversions: Optional[PositiveInt] = Field(
        default=None,
        description="목표 전환 수",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="미션 생성 시각",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="마지막 업데이트 시각",
    )

    @model_validator(mode="after")
    def _validate_dates(self) -> "Mission":
        """시작/종료 일자의 일관성을 검증합니다."""
        if self.expected_start and self.expected_end:
            if self.expected_end < self.expected_start:
                raise ValueError("expected_end must be greater than or equal to expected_start")
        return self

    def is_active(self, at: Optional[datetime] = None) -> bool:
        """
        주어진 시점에 미션이 활성 상태인지 여부를 반환합니다.

        활성 조건:
        - status 가 ACTIVE 이고
        - expected_start/expected_end 가 설정된 경우 그 범위 안에 포함
        """
        if self.status != MissionStatus.ACTIVE:
            return False

        now = at or datetime.utcnow()
        if self.expected_start and now < self.expected_start:
            return False
        if self.expected_end and now > self.expected_end:
            return False
        return True


class Reward(BaseModel):
    """
    특정 미션에 대해 크리에이터에게 지급되는 보상.
    """

    id: str = Field(..., description="보상 고유 ID")
    mission_id: str = Field(..., description="연결된 미션 ID")
    creator_id: str = Field(..., description="지급 대상 크리에이터 ID")

    amount: PositiveFloat = Field(..., description="지급 금액 (단일 지급 기준)")
    currency: str = Field(
        default="KRW",
        min_length=3,
        max_length=3,
        description="통화 코드 (예: KRW, USD)",
    )

    status: RewardStatus = Field(
        default=RewardStatus.PENDING,
        description="보상 상태",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="보상 레코드 생성 시각",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="마지막 상태 변경 시각",
    )

    def mark_paid(self) -> "Reward":
        """보상을 지급 완료 상태로 변경합니다."""
        self.status = RewardStatus.PAID
        self.updated_at = datetime.utcnow()
        return self


class BaseRepository(Protocol, Generic[TModel]):
    """
    간단한 CRUD 패턴을 위한 최소 저장소 인터페이스.

    구현체는 인메모리, 데이터베이스, Redis 등으로 확장될 수 있습니다.
    """

    def create(self, obj: TModel) -> TModel:  # pragma: no cover - interface only
        ...

    def get(self, obj_id: str) -> Optional[TModel]:  # pragma: no cover - interface only
        ...

    def list(self) -> Sequence[TModel]:  # pragma: no cover - interface only
        ...


class InMemoryRepository(Generic[TModel], BaseRepository[TModel]):
    """
    가장 단순한 인메모리 저장소 구현.

    - 프로토타입/테스트 용도로 사용합니다.
    - 프로덕션에서는 별도 영속 저장소로 교체해야 합니다.
    """

    def __init__(self) -> None:
        self._store: Dict[str, TModel] = {}

    def create(self, obj: TModel) -> TModel:
        obj_id = getattr(obj, "id", None)
        if not obj_id:
            raise ValueError("Object must have an 'id' field for InMemoryRepository")
        self._store[str(obj_id)] = obj
        return obj

    def get(self, obj_id: str) -> Optional[TModel]:
        return self._store.get(str(obj_id))

    def list(self) -> Sequence[TModel]:
        return list(self._store.values())

    def filter(self, predicate: Any) -> List[TModel]:
        """
        간단한 필터링 지원 (predicate: BaseModel -> bool).
        """
        return [obj for obj in self._store.values() if predicate(obj)]


class MissionRepository(InMemoryRepository[Mission]):
    """Mission 전용 인메모리 저장소."""

    def list_by_status(self, status: MissionStatus) -> List[Mission]:
        return [m for m in self._store.values() if isinstance(m, Mission) and m.status == status]


class CreatorRepository(InMemoryRepository[Creator]):
    """Creator 전용 인메모리 저장소."""

    def list_by_platform(self, platform: CreatorPlatform) -> List[Creator]:
        return [
            c
            for c in self._store.values()
            if isinstance(c, Creator)
            and (c.primary_platform == platform or platform in c.platforms)
        ]


class RewardRepository(InMemoryRepository[Reward]):
    """Reward 전용 인메모리 저장소."""

    def list_by_mission(self, mission_id: str) -> List[Reward]:
        return [
            r for r in self._store.values() if isinstance(r, Reward) and r.mission_id == mission_id
        ]


class InsightRepository(InMemoryRepository[Insight]):
    """Insight 전용 인메모리 저장소."""

    def list_by_source(self, source: InsightSource) -> List[Insight]:
        return [i for i in self._store.values() if isinstance(i, Insight) and i.source == source]


# -----------------------------------------------------------------------------
# Global in-memory repositories (prototype usage)
# -----------------------------------------------------------------------------

INSIGHT_REPOSITORY = InsightRepository()
MISSION_REPOSITORY = MissionRepository()
CREATOR_REPOSITORY = CreatorRepository()
REWARD_REPOSITORY = RewardRepository()


def _build_sentiment_summary(sentiment: Dict[str, Any]) -> Optional[str]:
    """공통 감성 요약 텍스트 생성 유틸리티."""
    if not sentiment:
        return None

    try:
        pos_pct = float(sentiment.get("positive_pct", 0.0))
        neu_pct = float(sentiment.get("neutral_pct", 0.0))
        neg_pct = float(sentiment.get("negative_pct", 0.0))
        return f"긍정 {pos_pct:.1f}% / 중립 {neu_pct:.1f}% / " f"부정 {neg_pct:.1f}%"
    except Exception:
        return None


def build_insight_from_result(
    source: InsightSource,
    result: Mapping[str, Any],
) -> Insight:
    """
    에이전트 실행 결과(dict 형태)를 Insight 도메인 객체로 변환합니다.

    Args:
        source: 인사이트를 생성한 에이전트 타입
        result: run_agent 또는 대시보드 executor가 반환한 결과 딕셔너리
    """
    analysis = result.get("analysis") or {}
    metrics = result.get("metrics") or {}
    sentiment = analysis.get("sentiment") or {}
    keywords_info = analysis.get("keywords") or {}

    # Top keywords를 텍스트 리스트로 추출
    top_keywords: List[str] = []
    top_kw_raw = keywords_info.get("top_keywords") if isinstance(keywords_info, dict) else None
    if isinstance(top_kw_raw, list):
        for kw in top_kw_raw:
            if isinstance(kw, dict) and "keyword" in kw:
                top_keywords.append(str(kw["keyword"]))
            elif isinstance(kw, str):
                top_keywords.append(kw)

    sentiment_summary = _build_sentiment_summary(sentiment)

    # 추천 액션은 현재 단계에서는 에이전트별 요약에서 직접 추출하지 않고
    # 후속 미션 추천 단계에서 활용합니다. 여기서는 빈 리스트로 둡니다.
    recommended_actions: List[str] = []

    insight_id = str(result.get("insight_id") or result.get("run_id") or uuid4().hex[:12])

    return Insight(
        id=insight_id,
        source=source,
        query=str(result.get("query", "")),
        time_window=result.get("time_window"),
        language=result.get("language"),
        sentiment_summary=sentiment_summary,
        top_keywords=top_keywords,
        summary=analysis.get("summary"),
        recommended_actions=recommended_actions,
        metrics={k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))},
        run_id=result.get("run_id"),
        report_path=str(result.get("report_md")) if result.get("report_md") else None,
    )


def save_insight_from_result(
    source: InsightSource,
    result: Mapping[str, Any],
) -> Insight:
    """
    실행 결과를 Insight로 변환하고 전역 인메모리 저장소에 저장합니다.

    Returns:
        저장된 Insight 인스턴스
    """
    insight = build_insight_from_result(source, result)
    INSIGHT_REPOSITORY.create(insight)
    return insight
