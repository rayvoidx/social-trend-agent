export enum MissionStatus {
  DRAFT = "draft",
  PLANNED = "planned",
  ACTIVE = "active",
  COMPLETED = "completed",
  CANCELLED = "cancelled",
}

export enum RewardStatus {
  PENDING = "pending",
  APPROVED = "approved",
  PAID = "paid",
  CANCELLED = "cancelled",
}

export enum InsightSource {
  NEWS_TREND = "news_trend_agent",
  VIRAL_VIDEO = "viral_video_agent",
  SOCIAL_TREND = "social_trend_agent",
}

export enum CreatorPlatform {
  YOUTUBE = "youtube",
  INSTAGRAM = "instagram",
  TIKTOK = "tiktok",
  X = "x",
  NAVER_BLOG = "naver_blog",
}

export interface Insight {
  id: string;
  source: InsightSource | string;
  query: string;
  time_window?: string | null;
  language?: string | null;
  sentiment_summary?: string | null;
  top_keywords: string[];
  summary?: string | null;
  recommended_actions?: string[];
  metrics: Record<string, number>;
  run_id?: string | null;
  report_path?: string | null;
  created_at?: Date;
}

export interface Creator {
  id: string;
  name: string;
  handle?: string | null;
  primary_platform: CreatorPlatform;
  platforms: CreatorPlatform[];
  category?: string | null;
  language?: string | null;
  followers?: number | null;
  avg_view_per_post?: number | null;
  avg_engagement_rate?: number | null;
  external_url?: string | null;
}

export interface Mission {
  id: string;
  title: string;
  description: string;
  insight_id?: string | null;
  target_audience?: string | null;
  platforms: CreatorPlatform[];
  expected_start?: Date | null;
  expected_end?: Date | null;
  status: MissionStatus;
  budget?: number | null;
  kpi_click_through_rate?: number | null;
  kpi_conversions?: number | null;
  created_at?: Date;
  updated_at?: Date;
}

export interface Reward {
  id: string;
  mission_id: string;
  creator_id: string;
  amount: number;
  currency: string;
  status: RewardStatus;
  created_at?: Date;
  updated_at?: Date;
}

// -----------------------------------------------------------------------------
// Simple in-memory repositories (prototype use only)
// -----------------------------------------------------------------------------

export interface HasId {
  id: string;
}

export class InMemoryRepository<T extends HasId> {
  private store = new Map<string, T>();

  create(obj: T): T {
    this.store.set(obj.id, obj);
    return obj;
  }

  get(id: string): T | undefined {
    return this.store.get(id);
  }

  list(): T[] {
    return Array.from(this.store.values());
  }
}

export class MissionRepository extends InMemoryRepository<Mission> {
  listByStatus(status: MissionStatus): Mission[] {
    return this.list().filter((m) => m.status === status);
  }
}

export class CreatorRepository extends InMemoryRepository<Creator> {
  listByPlatform(platform: CreatorPlatform): Creator[] {
    return this.list().filter(
      (c) =>
        c.primary_platform === platform || (c.platforms || []).includes(platform),
    );
  }
}

export class RewardRepository extends InMemoryRepository<Reward> {
  listByMission(missionId: string): Reward[] {
    return this.list().filter((r) => r.mission_id === missionId);
  }
}

export class InsightRepository extends InMemoryRepository<Insight> {
  listBySource(source: InsightSource): Insight[] {
    return this.list().filter((i) => i.source === source);
  }
}

export const INSIGHT_REPOSITORY = new InsightRepository();
export const MISSION_REPOSITORY = new MissionRepository();
export const CREATOR_REPOSITORY = new CreatorRepository();
export const REWARD_REPOSITORY = new RewardRepository();


