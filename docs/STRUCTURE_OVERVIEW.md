# Social Trend Agent - Repository Structure Overview

**Generated:** 2025-12-25
**Version:** 4.0.0

## Architecture Overview

This is a **monorepo** containing a **FastAPI backend** (port 8000) and **React frontend** (port 5173) with Redis caching and Prometheus monitoring for a multi-agent social trend analysis system.

### Technology Stack

**Backend:**
- FastAPI 0.115.7 with Pydantic v2 (2.11.7)
- LangChain 0.3.26 + LangGraph 0.2.0+ (agentic workflows)
- Python 3.11-3.12
- Redis 7 (caching & sessions)
- Prometheus (metrics)

**Frontend:**
- React 19.2.0
- Vite 5.4.21
- TypeScript 5.9.3
- TailwindCSS 3.4.18
- React Query 5.90.10

**Infrastructure:**
- Docker Compose (multi-service orchestration)
- Nginx (frontend proxy)
- Uvicorn (ASGI server)

---

## Directory Structure

```
social-trend-agent/
├── src/                          # Python backend source
│   ├── agents/                   # Multi-agent system
│   │   ├── news_trend/          # News trend analysis agent
│   │   ├── viral_video/         # Viral video analysis agent
│   │   ├── social_trend/        # Social media trend agent
│   │   └── orchestrator.py      # Agent routing & coordination
│   ├── api/                     # FastAPI routes & services
│   │   ├── routes/              # API endpoints
│   │   │   ├── dashboard.py    # Main API (804 lines) ⚠️
│   │   │   ├── n8n.py          # Workflow integration
│   │   │   └── mcp_routes.py   # MCP protocol routes
│   │   ├── schemas/             # Pydantic models
│   │   └── services/            # Business logic
│   ├── core/                    # Core infrastructure
│   │   ├── planning/            # Agent planning logic
│   │   ├── gateway.py          # LLM gateway
│   │   ├── routing.py          # Model routing
│   │   └── workflow.py         # LangGraph workflows
│   ├── domain/                  # Domain models
│   │   ├── models.py           # Insight, Mission models
│   │   └── planning/           # Planning schemas
│   ├── infrastructure/          # Infrastructure concerns
│   │   ├── cache.py            # In-memory/disk cache (192 lines)
│   │   ├── storage/            # Redis & Postgres
│   │   ├── monitoring/         # Prometheus metrics
│   │   ├── distributed.py      # Task queue & workers
│   │   └── rate_limiter.py     # Rate limiting
│   └── integrations/           # External services
│       ├── llm/                # LLM clients (OpenAI, Anthropic, Google)
│       ├── mcp/                # Model Context Protocol
│       ├── social/             # Social media APIs
│       └── retrieval/          # Pinecone vector store
├── apps/
│   ├── web/                    # React frontend
│   │   ├── src/
│   │   │   ├── components/     # React components
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   ├── AnalysisForm.tsx
│   │   │   │   ├── ResultCard.tsx
│   │   │   │   └── MissionRecommendations.tsx
│   │   │   ├── api/           # API clients
│   │   │   ├── types/         # TypeScript types
│   │   │   └── main.tsx       # Entry point
│   │   ├── Dockerfile         # Multi-stage build ✅
│   │   ├── vite.config.ts     # Vite config (12 lines) ⚠️
│   │   └── package.json
│   └── node/                  # Node.js backend (optional)
├── tests/                     # Test suite
│   ├── integration/           # Integration tests (30 tests)
│   │   ├── test_api_server.py
│   │   ├── test_news_agent_integration.py
│   │   └── test_social_trend_agent.py
│   └── unit/                  # Unit tests (minimal coverage)
├── config/                    # Configuration
│   ├── prometheus.yml        # Metrics config
│   ├── mcp/                  # MCP server configs
│   └── otel/                 # OpenTelemetry
├── deploy/                   # Deployment scripts
│   ├── n8n/                  # Workflow definitions
│   └── scripts/
├── Dockerfile                # Backend (single-stage) ⚠️
├── docker-compose.yaml       # Multi-service orchestration
└── pyproject.toml           # Python dependencies
```

---

## Key Components

### 1. API Layer (`src/api/routes/dashboard.py`)

**Main endpoints:**
- `GET /api/health` - Health check
- `POST /api/tasks` - Submit analysis task
- `GET /api/tasks/{task_id}` - Task status
- `GET /api/insights` - List insights
- `POST /api/missions/recommend` - Mission recommendations
- `WS /ws/metrics` - Real-time metrics stream

**Issues:**
- ❌ 804 lines (monolithic)
- ❌ No Redis caching on endpoints
- ❌ Large response payloads not paginated

### 2. Caching Layer (`src/infrastructure/cache.py`)

**Current implementation:**
- ✅ `SimpleCache` - In-memory TTL cache
- ✅ `DiskCache` - Persistent file-based cache
- ❌ **NO Redis integration** (despite Redis running in docker-compose)

**Needed:**
- Add `RedisCache` adapter
- Integrate with FastAPI dependency injection
- Cache expensive LLM calls

### 3. Frontend (`apps/web`)

**Components:**
- Dashboard, AnalysisForm, ResultCard, MissionRecommendations
- Uses React Query for data fetching
- TailwindCSS for styling

**Issues:**
- ❌ Minimal Vite optimization (basic config)
- ❌ No component lazy loading
- ❌ No E2E tests (Cypress)

### 4. Docker Setup

**Current:**
```yaml
services:
  api:       # FastAPI (port 8000) - single-stage Dockerfile ⚠️
  web:       # React (port 5173) - multi-stage ✅
  redis:     # Redis 7 (port 6380) - with healthcheck ✅
  prometheus:# Prometheus (port 9091) - no healthcheck ⚠️
```

**Issues:**
- ❌ Backend Dockerfile is single-stage (large image)
- ⚠️ Prometheus has no healthcheck

---

## Testing Status

### Current Coverage
- **Integration Tests:** 30 tests
  - API server tests (12)
  - News agent tests (11)
  - Social agent tests (7)
- **Unit Tests:** Minimal (mostly `__init__.py` files)
- **E2E Tests:** None

### Gaps
- ❌ No coverage report configured
- ❌ Core modules (`cache.py`, `routing.py`, `gateway.py`) untested
- ❌ Frontend has no tests
- ❌ No Cypress setup

**Target:** 80% pytest coverage + Cypress E2E

---

## Performance Optimizations Needed

### Backend
1. **Redis Caching**
   - Cache `/api/insights` (frequently read)
   - Cache `/api/tasks` (reduce DB hits)
   - Cache LLM responses (expensive)

2. **Endpoint Refactoring**
   - Split `dashboard.py` into smaller route files
   - Add async Redis cache decorator
   - Implement response compression

### Frontend
1. **Code Splitting**
   - Lazy load Dashboard, MissionRecommendations
   - Dynamic imports for heavy components

2. **Vite Optimization**
   - Configure chunk size limits
   - Enable Rollup optimizations
   - Add compression plugin

### Docker
1. **Multi-stage Backend Build**
   - Separate build and runtime stages
   - Use `python:3.11-slim` for final stage
   - Reduce image size ~60%

2. **Healthchecks**
   - Add Prometheus healthcheck
   - Improve startup checks

---

## Agentic Workflow Architecture

```
User Query
    ↓
Orchestrator (src/agents/orchestrator.py)
    ↓
Router → Planner → Workers
    ↓
┌─────────────┬─────────────┬─────────────┐
│ news_trend  │ viral_video │social_trend │
└─────────────┴─────────────┴─────────────┘
    ↓
Merger (if multi-agent)
    ↓
Insight → Mission → Creator Recommendation
```

**Agents:**
1. `news_trend_agent` - Analyzes news articles + trends
2. `viral_video_agent` - Analyzes YouTube/TikTok virality
3. `social_trend_agent` - X/Instagram trend analysis

**LangGraph Workflow:**
- Planning → Collection → Normalization → Analysis → Reporting

---

## Next Steps (Prioritized)

### Phase 1: Backend Optimization (Week 1)
- [ ] Implement Redis caching adapter
- [ ] Add caching to top 5 endpoints
- [ ] Refactor `dashboard.py` into modular routes

### Phase 2: Docker & Infrastructure (Week 1)
- [ ] Convert backend Dockerfile to multi-stage
- [ ] Add healthchecks to all services
- [ ] Test deployment with optimizations

### Phase 3: Frontend Optimization (Week 2)
- [ ] Extract reusable components
- [ ] Configure Vite for production
- [ ] Add lazy loading

### Phase 4: Testing (Week 2)
- [ ] Write unit tests for core modules
- [ ] Set up Cypress E2E framework
- [ ] Configure pytest coverage (target 80%)
- [ ] Add GitHub Actions CI/CD

---

## Metrics & Monitoring

**Current:**
- ✅ Prometheus scraping `/metrics` endpoint
- ✅ Custom metrics in `infrastructure/monitoring/`
- ✅ Task queue metrics (executor stats)

**Improvements:**
- Add Redis cache hit/miss metrics
- Track LLM latency per provider
- Add frontend performance monitoring

---

## Dependencies Summary

**Backend (requirements.txt):**
- fastapi, uvicorn, pydantic
- langchain, langgraph (0.3.x)
- openai, anthropic, google-generativeai
- redis, pinecone
- prometheus-client, psutil

**Frontend (package.json):**
- react 19.2.0, react-dom
- @tanstack/react-query
- axios, lucide-react
- tailwindcss, vite

**DevOps:**
- Docker, docker-compose
- pytest, pytest-asyncio
- black (code formatter)

---

## Contact & Resources

- **Docs:** `/docs` (prompts, style guides)
- **Artifacts:** `/artifacts/{agent_name}` (generated reports)
- **Logs:** `/logs`
- **Config:** `/config` (YAML configs for services)

---

## Legend
- ✅ Implemented & working
- ⚠️ Partial or needs improvement
- ❌ Missing or requires implementation
