# CLAUDE.md
## Project Overview
FastAPI(8000) + React(5173) + Redis + Prometheus social trend agent

## Coding Standards
- FastAPI: Pydantic v2, async/await
- React: Vite 5173, TypeScript
- Docker: Multi-stage, healthchecks
- Goals: Agentic workflow 적용, 성능 20%↑, 테스트 커버리지 80%↑

## Sub-agents
/planner: 아키텍처 분석
/api-agent: FastAPI 엔드포인트 최적화  
/web-agent: React 컴포넌트 리팩토링
/docker-agent: 컨테이너 보안/스케일링
/test-agent: pytest/cypress 자동화