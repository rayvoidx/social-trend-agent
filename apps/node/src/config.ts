import dotenv from "dotenv";

dotenv.config();

export const PYTHON_API_BASE_URL =
  process.env.PYTHON_API_BASE_URL || "http://localhost:8000";

export const NODE_PORT = Number(process.env.NODE_PORT || 3001);


