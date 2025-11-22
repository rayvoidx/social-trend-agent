"""
Mission & Creator recommendation services.

도메인 모델(`backend.domain`)을 기반으로 인사이트에서 미션을 생성하고,
미션에 적합한 크리에이터를 추천하는 간단한 규칙 기반 서비스 레이어입니다.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, cast
from uuid import uuid4

from src.domain.models import (
    CREATOR_REPOSITORY,
    MISSION_REPOSITORY,
    Creator,
    CreatorPlatform,
    Insight,
    Mission,
    MissionStatus,
)


def _default_platforms_for_insight(insight: Insight) -> List[CreatorPlatform]:
    """인사이트 소스/키워드를 기반으로 기본 플랫폼 후보를 추정합니다."""
    # 간단한 휴리스틱: 소스별 기본값
    if "youtube" in (kw.lower() for kw in insight.top_keywords):
        return [CreatorPlatform.YOUTUBE]
    if "tiktok" in (kw.lower() for kw in insight.top_keywords):
        return [CreatorPlatform.TIKTOK]
    if "instagram" in (kw.lower() for kw in insight.top_keywords):
        return [CreatorPlatform.INSTAGRAM]

    # 키워드에 소셜 관련 단어가 많다면 소셜 위주
    social_tokens = {"sns", "소셜", "instagram", "tik tok", "shorts", "릴스"}
    if any(tok in kw.lower() for kw in insight.top_keywords for tok in social_tokens):
        return [CreatorPlatform.INSTAGRAM, CreatorPlatform.YOUTUBE]

    # 기본값
    return [CreatorPlatform.YOUTUBE]


def generate_missions_from_insight(insight: Insight) -> List[Mission]:
    """
    인사이트를 기반으로 1~2개의 미션을 생성하고 저장소에 저장합니다.

    현재는 간단한 규칙 기반 템플릿을 사용하며,
    향후 LLM 기반 미션 제안으로 확장할 수 있습니다.
    """
    platforms = _default_platforms_for_insight(insight)
    now = datetime.utcnow()

    missions: List[Mission] = []

    # 미션 1: 트렌드 기반 콘텐츠 제작
    missions.append(
        Mission(
            id=f"m_{uuid4().hex[:10]}",
            title=f"[{insight.query}] 트렌드 콘텐츠 제작",
            description=(
                f"최근 '{insight.query}' 관련 트렌드 및 주요 키워드를 반영한 콘텐츠를 제작합니다. "
                f"주요 키워드: {', '.join(insight.top_keywords[:5]) or 'N/A'}"
            ),
            insight_id=insight.id,
            target_audience="일반 소비자",
            platforms=platforms,
            expected_start=now,
            expected_end=now + timedelta(days=7),
            status=MissionStatus.PLANNED,
        )
    )

    # 미션 2: 필요 시 인사이트 기반 심화 캠페인
    if insight.metrics.get("actionability", 0.0) >= 0.8:
        missions.append(
            Mission(
                id=f"m_{uuid4().hex[:10]}",
                title=f"[{insight.query}] 심화 캠페인",
                description=(
                    "인사이트에서 제안된 실행 권고안을 바탕으로 최소 2주 이상 진행되는 "
                    "심화 캠페인을 설계하고 실행합니다."
                ),
                insight_id=insight.id,
                target_audience="잠재 고객/기존 고객",
                platforms=platforms,
                expected_start=now + timedelta(days=3),
                expected_end=now + timedelta(days=21),
                status=MissionStatus.PLANNED,
            )
        )

    # 저장소에 persist
    for mission in missions:
        MISSION_REPOSITORY.create(mission)

    return missions


def ensure_sample_creators_seeded() -> None:
    """
    샘플 크리에이터 데이터를 인메모리 저장소에 채워 넣습니다.

    - 실제 서비스에서는 별도 DB/연동을 통해 관리해야 합니다.
    """
    # 이미 데이터가 있다면 스킵
    if CREATOR_REPOSITORY.list():
        return

    samples = [
        Creator(
            id="cr_youtube_1",
            name="Tech Review KR",
            handle="@techreviewkr",
            primary_platform=CreatorPlatform.YOUTUBE,
            platforms=[CreatorPlatform.YOUTUBE],
            category="tech",
            language="ko",
            followers=250_000,
            avg_view_per_post=80_000,
            avg_engagement_rate=0.06,
        ),
        Creator(
            id="cr_youtube_2",
            name="Daily Vlog Korea",
            handle="@dailyvlogkr",
            primary_platform=CreatorPlatform.YOUTUBE,
            platforms=[CreatorPlatform.YOUTUBE, CreatorPlatform.INSTAGRAM],
            category="lifestyle",
            language="ko",
            followers=150_000,
            avg_view_per_post=40_000,
            avg_engagement_rate=0.08,
        ),
        Creator(
            id="cr_insta_1",
            name="Insta Beauty Lab",
            handle="@instabeautylab",
            primary_platform=CreatorPlatform.INSTAGRAM,
            platforms=[CreatorPlatform.INSTAGRAM],
            category="beauty",
            language="ko",
            followers=320_000,
            avg_view_per_post=50_000,
            avg_engagement_rate=0.09,
        ),
        Creator(
            id="cr_tiktok_1",
            name="Fun Short Clips",
            handle="@funshorts",
            primary_platform=CreatorPlatform.TIKTOK,
            platforms=[CreatorPlatform.TIKTOK],
            category="entertainment",
            language="ko",
            followers=500_000,
            avg_view_per_post=120_000,
            avg_engagement_rate=0.12,
        ),
    ]

    for creator in samples:
        CREATOR_REPOSITORY.create(creator)


def recommend_creators_for_mission(
    mission: Mission,
    limit: int = 5,
) -> List[Creator]:
    """
    미션에 적합한 크리에이터를 추천합니다.

    간단한 규칙:
    - 미션 대상 플랫폼과 크리에이터 플랫폼이 겹치는 경우 우선
    - 팔로워 수, 평균 조회수, 참여율 기준 정렬
    """
    ensure_sample_creators_seeded()

    all_creators = [cast(Creator, c) for c in CREATOR_REPOSITORY.list()]
    if not mission.platforms:
        # 플랫폼 정보가 없다면 전체에서 상위 크리에이터 반환
        sorted_creators = sorted(
            all_creators,
            key=lambda c: (
                getattr(c, "followers", 0) or 0,
                getattr(c, "avg_view_per_post", 0) or 0,
            ),
            reverse=True,
        )
        return list(sorted_creators)[:limit]

    def score_creator(c: Creator) -> int:
        score = 0
        # 플랫폼 매칭 가중치
        if any(p in mission.platforms for p in c.platforms) or c.primary_platform in mission.platforms:
            score += 100
        # 팔로워 / 조회수 / 참여율
        score += int((c.followers or 0) / 10_000)
        score += int((c.avg_view_per_post or 0) / 5_000)
        score += int(((c.avg_engagement_rate or 0.0) * 100))
        return score

    scored = sorted(all_creators, key=score_creator, reverse=True)
    return list(scored)[:limit]


