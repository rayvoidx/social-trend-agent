import express from "express";
import { createApp } from "./app";
import { NODE_PORT, PYTHON_API_BASE_URL } from "./config";

// Express 앱 구성은 app.ts에서 담당
const app = createApp();
const PORT = NODE_PORT;

// 서버 부트스트랩
app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(
    `Node TypeScript API running on http://localhost:${PORT} (proxy -> ${PYTHON_API_BASE_URL})`,
  );
});

