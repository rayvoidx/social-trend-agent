import { z } from "zod";
import { InsightSchema } from "./insight";

export const MissionRecommendRequestSchema = z.object({
  insight: InsightSchema,
  target_audience: z.string().optional(),
  budget: z.number().optional(),
});

export type MissionRecommendRequest = z.infer<
  typeof MissionRecommendRequestSchema
>;

