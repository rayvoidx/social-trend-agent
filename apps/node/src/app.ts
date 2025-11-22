import express, { Request, Response } from "express";
import cors from "cors";
import { NODE_PORT, PYTHON_API_BASE_URL } from "./config";
import { insightsRouter } from "./routes/insights";
import { missionsRouter } from "./routes/missions";

export function createApp() {
  const app = express();

  app.use(cors());
  app.use(express.json());

  // Health check
  app.get("/health", (_req: Request, res: Response) => {
    res.json({
      status: "ok",
      service: "node-api",
      port: NODE_PORT,
      pythonApiBaseUrl: PYTHON_API_BASE_URL,
    });
  });

  // Feature routes
  app.use("/insights", insightsRouter);
  app.use("/missions", missionsRouter);

  return app;
}


