import { Router, Request, Response } from "express";
import axios from "axios";
import { PYTHON_API_BASE_URL } from "../config";
import { listInsightsQuerySchema } from "../schemas/insight";

export const insightsRouter = Router();

// GET /insights
insightsRouter.get("/", async (req: Request, res: Response) => {
  try {
    const parsedQuery = listInsightsQuerySchema.parse(req.query);
    const response = await axios.get(`${PYTHON_API_BASE_URL}/api/insights`, {
      params: parsedQuery,
    });
    res.status(response.status).json(response.data);
  } catch (err: any) {
    if (err.name === "ZodError") {
      return res.status(400).json({ message: "Invalid query parameters", issues: err.issues });
    }
    const status = err.response?.status ?? 500;
    const detail =
      err.response?.data ?? { message: "Failed to fetch insights from Python API" };
    res.status(status).json(detail);
  }
});

// GET /insights/:id
insightsRouter.get("/:id", async (req: Request, res: Response) => {
  try {
    const response = await axios.get(
      `${PYTHON_API_BASE_URL}/api/insights/${req.params.id}`,
    );
    res.status(response.status).json(response.data);
  } catch (err: any) {
    const status = err.response?.status ?? 500;
    const detail =
      err.response?.data ??
      { message: "Failed to fetch insight detail from Python API" };
    res.status(status).json(detail);
  }
});


