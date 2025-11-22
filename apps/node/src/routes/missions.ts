import { Router, Request, Response } from "express";
import { MissionRecommendRequestSchema } from "../schemas/mission";
import {
  generateMissionsFromInsight,
  recommendCreatorsForMission,
} from "../services/missionService";

export const missionsRouter = Router();

// POST /missions/recommend
// Body: { insight: Insight, target_audience?, budget? }
missionsRouter.post("/recommend", async (req: Request, res: Response) => {
  try {
    const body = MissionRecommendRequestSchema.parse(req.body);

    const missions = generateMissionsFromInsight(body.insight);

    // 선택적으로 요청에서 타깃/예산 덮어쓰기
    missions.forEach((m) => {
      if (body.target_audience) m.target_audience = body.target_audience;
      if (body.budget != null) m.budget = body.budget;
    });

    const recommendations = missions.map((m) => ({
      mission: m,
      creators: recommendCreatorsForMission(m),
    }));

    res.status(200).json({
      insight_id: body.insight.id,
      count: recommendations.length,
      recommendations,
    });
  } catch (err: any) {
    if (err.name === "ZodError") {
      return res
        .status(400)
        .json({ message: "Invalid request body", issues: err.issues });
    }
    res
      .status(500)
      .json({ message: "Failed to generate mission recommendations", error: String(err) });
  }
});

