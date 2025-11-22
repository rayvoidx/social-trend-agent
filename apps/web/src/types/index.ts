export interface AnalysisRequest {
  agent_type: 'news_trend_agent' | 'viral_video_agent' | 'social_trend_agent';
  query: string;
  time_window?: string;
  language?: string;
  market?: string;
  platforms?: string[];
  sources?: string[];
  params?: Record<string, unknown>;
}

export interface SentimentData {
  positive: number;
  neutral: number;
  negative: number;
  positive_pct: number;
  neutral_pct: number;
  negative_pct: number;
}

export interface KeywordData {
  keyword: string;
  count: number;
}

export interface AnalysisResult {
  query: string;
  time_window: string;
  language?: string;
  normalized?: unknown;
  report_md?: string;
  analysis?: unknown;
  metrics?: Record<string, unknown>;
  run_id: string;
  insight_id?: string;
  sentiment?: SentimentData;
  keywords?: KeywordData[];
  summary?: string;
  report_path?: string;
  created_at?: string;
  error?: string;
}

export interface TaskStatus {
  task_id: string;
  agent_name: string;
  query: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  created_at: number;
  started_at?: number;
  completed_at?: number;
  duration?: number;
  result?: AnalysisResult;
  error?: string;
}

export interface CreatorRecommendation {
  id: string;
  name: string;
  primary_platform: string;
  followers?: number | null;
  avg_view_per_post?: number | null;
  avg_engagement_rate?: number | null;
}

export interface Mission {
  id: string;
  title: string;
  description: string;
  platforms: string[];
  target_audience?: string | null;
  budget?: number | null;
}

export interface MissionRecommendation {
  mission: Mission;
  creators: CreatorRecommendation[];
}

export interface MissionRecommendationResponse {
  insight_id: string;
  count: number;
  recommendations: MissionRecommendation[];
}
