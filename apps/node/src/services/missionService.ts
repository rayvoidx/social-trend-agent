import { v4 as uuidv4 } from "uuid";
import {
  CREATOR_REPOSITORY,
  Creator,
  CreatorPlatform,
  Insight,
  MISSION_REPOSITORY,
  Mission,
  MissionStatus,
} from "../domain/models";

function defaultPlatformsForInsight(insight: Insight): CreatorPlatform[] {
  // 간단한 휴리스틱: 키워드에 플랫폼 이름이 들어가면 매칭
  const lowerKeywords = (insight.top_keywords || []).map((k) => k.toLowerCase());

  if (lowerKeywords.some((k) => k.includes("youtube"))) {
    return [CreatorPlatform.YOUTUBE];
  }
  if (lowerKeywords.some((k) => k.includes("tiktok"))) {
    return [CreatorPlatform.TIKTOK];
  }
  if (lowerKeywords.some((k) => k.includes("instagram"))) {
    return [CreatorPlatform.INSTAGRAM];
  }

  const socialTokens = ["sns", "소셜", "instagram", "tik tok", "shorts", "릴스"];
  if (
    lowerKeywords.some((kw) => socialTokens.some((token) => kw.includes(token)))
  ) {
    return [CreatorPlatform.INSTAGRAM, CreatorPlatform.YOUTUBE];
  }

  return [CreatorPlatform.YOUTUBE];
}

export function generateMissionsFromInsight(insight: Insight): Mission[] {
  const platforms = defaultPlatformsForInsight(insight);
  const now = new Date();

  const missions: Mission[] = [];

  missions.push({
    id: `m_${uuidv4().slice(0, 10)}`,
    title: `[${insight.query}] 트렌드 콘텐츠 제작`,
    description: `최근 '${insight.query}' 관련 트렌드 및 주요 키워드를 반영한 콘텐츠를 제작합니다. 주요 키워드: ${
      insight.top_keywords.slice(0, 5).join(", ") || "N/A"
    }`,
    insight_id: insight.id,
    target_audience: "일반 소비자",
    platforms,
    expected_start: now,
    expected_end: new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000),
    status: MissionStatus.PLANNED,
    budget: null,
    kpi_click_through_rate: null,
    kpi_conversions: null,
    created_at: now,
    updated_at: now,
  });

  const actionability = insight.metrics?.actionability ?? 0;
  if (actionability >= 0.8) {
    missions.push({
      id: `m_${uuidv4().slice(0, 10)}`,
      title: `[${insight.query}] 심화 캠페인`,
      description:
        "인사이트에서 제안된 실행 권고안을 바탕으로 최소 2주 이상 진행되는 심화 캠페인을 설계하고 실행합니다.",
      insight_id: insight.id,
      target_audience: "잠재 고객/기존 고객",
      platforms,
      expected_start: new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000),
      expected_end: new Date(now.getTime() + 21 * 24 * 60 * 60 * 1000),
      status: MissionStatus.PLANNED,
      budget: null,
      kpi_click_through_rate: null,
      kpi_conversions: null,
      created_at: now,
      updated_at: now,
    });
  }

  missions.forEach((m) => MISSION_REPOSITORY.create(m));
  return missions;
}

export function ensureSampleCreatorsSeeded(): void {
  if (CREATOR_REPOSITORY.list().length > 0) return;

  const samples: Creator[] = [
    {
      id: "cr_youtube_1",
      name: "Tech Review KR",
      handle: "@techreviewkr",
      primary_platform: CreatorPlatform.YOUTUBE,
      platforms: [CreatorPlatform.YOUTUBE],
      category: "tech",
      language: "ko",
      followers: 250_000,
      avg_view_per_post: 80_000,
      avg_engagement_rate: 0.06,
    },
    {
      id: "cr_youtube_2",
      name: "Daily Vlog Korea",
      handle: "@dailyvlogkr",
      primary_platform: CreatorPlatform.YOUTUBE,
      platforms: [CreatorPlatform.YOUTUBE, CreatorPlatform.INSTAGRAM],
      category: "lifestyle",
      language: "ko",
      followers: 150_000,
      avg_view_per_post: 40_000,
      avg_engagement_rate: 0.08,
    },
    {
      id: "cr_insta_1",
      name: "Insta Beauty Lab",
      handle: "@instabeautylab",
      primary_platform: CreatorPlatform.INSTAGRAM,
      platforms: [CreatorPlatform.INSTAGRAM],
      category: "beauty",
      language: "ko",
      followers: 320_000,
      avg_view_per_post: 50_000,
      avg_engagement_rate: 0.09,
    },
    {
      id: "cr_tiktok_1",
      name: "Fun Short Clips",
      handle: "@funshorts",
      primary_platform: CreatorPlatform.TIKTOK,
      platforms: [CreatorPlatform.TIKTOK],
      category: "entertainment",
      language: "ko",
      followers: 500_000,
      avg_view_per_post: 120_000,
      avg_engagement_rate: 0.12,
    },
  ];

  samples.forEach((c) => CREATOR_REPOSITORY.create(c));
}

export function recommendCreatorsForMission(
  mission: Mission,
  limit = 5,
): Creator[] {
  ensureSampleCreatorsSeeded();

  const allCreators = CREATOR_REPOSITORY.list();

  if (!mission.platforms || mission.platforms.length === 0) {
    return allCreators
      .slice()
      .sort((a, b) => {
        const aScore =
          (a.followers ?? 0) + (a.avg_view_per_post ?? 0) * 2 +
          ((a.avg_engagement_rate ?? 0) * 10000);
        const bScore =
          (b.followers ?? 0) + (b.avg_view_per_post ?? 0) * 2 +
          ((b.avg_engagement_rate ?? 0) * 10000);
        return bScore - aScore;
      })
      .slice(0, limit);
  }

  const scoreCreator = (c: Creator): number => {
    let score = 0;
    if (
      c.platforms?.some((p) => mission.platforms.includes(p)) ||
      mission.platforms.includes(c.primary_platform)
    ) {
      score += 100;
    }
    score += Math.floor((c.followers ?? 0) / 10_000);
    score += Math.floor((c.avg_view_per_post ?? 0) / 5_000);
    score += Math.floor((c.avg_engagement_rate ?? 0) * 100);
    return score;
  };

  return allCreators
    .slice()
    .sort((a, b) => scoreCreator(b) - scoreCreator(a))
    .slice(0, limit);
}


