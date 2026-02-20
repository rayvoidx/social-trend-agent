# Node API Gateway (Legacy - Not Active)

This directory contains a TypeScript API gateway developed during early architecture exploration.

**Status**: Inactive. The current architecture uses the Python FastAPI gateway (`src/api/`) instead.

## Why It's Here

Kept for reference in case hybrid architecture patterns (Node + Python) become relevant in future iterations.

## Current Architecture

All API routing, MCP integration, and agent orchestration run through:

- **FastAPI** (`src/api/routes/dashboard.py`) — Main API server on port 8000
- **React 19** (`apps/web/`) — Frontend on port 5173

This Node gateway is **not started** by `main.py` or `docker-compose.yaml`.
