import { z } from "zod";

export const listInsightsQuerySchema = z.object({
  source: z.string().optional(),
  query: z.string().optional(),
  limit: z
    .union([z.string(), z.number()])
    .transform((v) => Number(v))
    .pipe(z.number().int().min(1).max(200))
    .optional(),
});

export const InsightSummarySchema = z.object({
  id: z.string(),
  source: z.string(),
  query: z.string(),
  time_window: z.string().nullable().optional(),
  language: z.string().nullable().optional(),
  sentiment_summary: z.string().nullable().optional(),
  top_keywords: z.array(z.string()).default([]),
  run_id: z.string().nullable().optional(),
  report_path: z.string().nullable().optional(),
  created_at: z.number(),
});

export type InsightSummary = z.infer<typeof InsightSummarySchema>;

// 전체 Insight 구조 (Node 내 미션 추천용)
export const InsightSchema = z.object({
  id: z.string(),
  source: z.string(),
  query: z.string(),
  time_window: z.string().nullable().optional(),
  language: z.string().nullable().optional(),
  sentiment_summary: z.string().nullable().optional(),
  top_keywords: z.array(z.string()).default([]),
  summary: z.string().nullable().optional(),
  recommended_actions: z.array(z.string()).optional().default([]),
  metrics: z.record(z.number()).optional().default({}),
  run_id: z.string().nullable().optional(),
  report_path: z.string().nullable().optional(),
});

