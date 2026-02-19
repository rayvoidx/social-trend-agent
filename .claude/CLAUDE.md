# CLAUDE.md

## Project Overview

FastAPI(8000) + React(5173) + Redis + Prometheus social trend agent
LangGraph 기반 멀티 에이전트 시스템 (News, Viral Video, Social Trend)

## Architecture

```
User → FastAPI(:8000) → Orchestrator → LangGraph Agents
                                         ├── news_trend_agent
                                         ├── viral_video_agent
                                         └── social_trend_agent
       React(:5173) ←→ API ←→ Redis(:6380)
       Prometheus(:9091) ← /metrics
       MCP: Brave Search, Supadata
```

## Coding Standards

- FastAPI: Pydantic v2, async/await, DI pattern
- React: Vite 5173, TypeScript strict, TailwindCSS
- Docker: Multi-stage builds, healthchecks, non-root user
- Python: 3.11+, type hints, structured logging
- Tests: pytest, asyncio_mode=auto, coverage target 80%

## Goals

- Agentic workflow 적용 (LangGraph + MCP)
- 성능 20% 향상 (API 응답, 캐시 히트율, 에이전트 실행 시간)
- 테스트 커버리지 30% → 80%

---

## Claude Code Agent Teams

Agent Teams 활성화됨 (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`).
teammateMode: `tmux` (split-pane, Shift+Down으로 이동).

### Team Structure

```
Lead (You) ─── Delegate Mode (Shift+Tab) ───→ 태스크 분배만 수행
    │
    ├── Backend Teammate     : FastAPI, Infrastructure, Pydantic v2
    ├── Frontend Teammate    : React, TypeScript, TailwindCSS
    ├── Data/AI Teammate     : LangGraph, MCP, LLM, RAG pipeline
    ├── QA Teammate          : pytest, 커버리지 80%, 회귀 테스트
    ├── Performance Teammate : Prometheus, 성능 20% 향상
    ├── DevOps Teammate      : Docker, CI/CD, GitHub Actions
    └── Security Teammate    : OWASP, 시크릿, 의존성 보안
```

### How to Start a Team

자연어로 팀을 요청하면 됩니다:

```
새 기능 개발 팀을 만들어줘. Backend, Frontend, QA 3명으로 구성.
각 teammate는 plan approval 필요. Sonnet 모델 사용.
```

```
캐싱 레이어 개선 팀을 만들어줘:
- Backend teammate: src/infrastructure/cache.py 리팩토링
- Performance teammate: 캐시 히트율 프로파일링
- QA teammate: 캐시 관련 테스트 작성
파일 충돌 없도록 각자 다른 파일만 수정할 것.
```

### Team Prompt Templates

#### Feature Development (3-4 teammates)

```
Create an agent team for: [태스크 설명]

Spawn teammates:
- Backend: [src/api/ or src/infrastructure/ 관련 작업]. Pydantic v2, async/await 필수.
- Frontend: [apps/web/src/ 관련 작업]. TypeScript strict, TailwindCSS.
- QA: 변경된 파일의 테스트 작성. pytest --cov=src 실행. 커버리지 80% 목표.

Require plan approval before implementation.
Each teammate owns different files - no overlapping edits.
Wait for all teammates to complete before synthesizing.
```

#### Bug Fix (2 teammates)

```
Create an agent team to fix: [버그 설명]

Spawn 2 teammates:
- Investigator: 원인 분석. src/ 코드 탐색, 로그 확인, 재현 시나리오.
- Fixer: Investigator 결과 기반으로 수정 구현 + 회귀 테스트 작성.

Use task dependencies: Fixer는 Investigator 완료 후 시작.
```

#### Performance Optimization (2-3 teammates)

```
Create an agent team for performance optimization:

Spawn teammates:
- Profiler: src/infrastructure/monitoring/, Prometheus 메트릭 분석, 병목 식별.
- Optimizer: Profiler 발견 기반으로 src/infrastructure/cache.py, src/agents/ 최적화.
- QA: 최적화 전후 벤치마크 + 회귀 테스트.

Target: API 응답 시간 20% 감소, 캐시 히트율 80%+.
```

#### Security Audit (2 teammates)

```
Create an agent team for security review:

Spawn teammates:
- Auditor: OWASP Top 10 기준 src/ 전체 스캔. 시크릿 노출, 입력 검증, 인증 확인.
- Fixer: Auditor 발견 기반으로 취약점 수정. 수정 후 재검증.

Critical/High 이슈 우선 처리.
```

#### Full Release (5+ teammates)

```
Create an agent team for release preparation:

Spawn teammates:
- Backend: API 엔드포인트 최종 점검 및 수정
- Frontend: React 컴포넌트 최종 점검 및 수정
- QA: 전체 테스트 실행, 커버리지 확인
- Security: OWASP 점검, pip audit, npm audit
- DevOps: Docker 빌드 확인, CI 파이프라인 검증

Require plan approval for all teammates.
QA와 Security는 다른 teammate 완료 후 시작 (task dependencies).
```

### Key Rules for Teammates

1. **File Ownership**: 각 teammate는 서로 다른 파일만 수정. 동일 파일 동시 수정 금지.
2. **Plan Approval**: 복잡한 태스크는 `Require plan approval` 사용.
3. **Delegate Mode**: Lead가 직접 구현하지 않도록 `Shift+Tab`으로 Delegate 모드 전환.
4. **Task Dependencies**: 순차 작업은 `depends on` 명시.
5. **Teammate당 5-6 tasks**: 너무 크거나 작지 않게 분할.

### Navigation (tmux split-pane)

- `Shift+Down` - 다음 teammate로 이동
- `Shift+Up` - 이전 teammate로 이동
- `Ctrl+T` - Task list 토글
- `Escape` - teammate 현재 턴 중단
- Click pane - 해당 teammate와 직접 상호작용

### Claude Squad (Alternative)

독립 세션 + git worktree 격리가 필요할 때:

```bash
# 설치
brew install claude-squad

# 실행
cs                    # TUI 실행
n                     # 새 세션
N                     # 프롬프트와 함께 새 세션
↑/↓                   # 세션 간 이동
↵                     # 세션 attach
tab                   # preview/diff 전환
s                     # commit & push
D                     # 세션 삭제
```

---

### Execution Agents (agents/ prompts)

| Agent       | Role                | Scope                                                             |
| ----------- | ------------------- | ----------------------------------------------------------------- |
| Backend     | Backend Lead        | FastAPI, Pydantic, Infrastructure (src/api/, src/infrastructure/) |
| Frontend    | Frontend Lead       | React, TypeScript, TailwindCSS (apps/web/)                        |
| Data/AI     | Data & AI Pipeline  | LangGraph, MCP, LLM, RAG (src/agents/, src/integrations/)         |
| QA          | QA Lead             | pytest, Cypress, 커버리지 80% (tests/)                            |
| Performance | Performance         | Prometheus, 성능 20% 향상 (src/infrastructure/monitoring/)        |
| DevOps      | Container & CI/CD   | Docker, GitHub Actions (Dockerfile, .github/workflows/)           |
| Security    | Security Specialist | OWASP, 시크릿, 의존성 보안                                        |

### Diagnostic Skills (읽기 전용 점검)

| Skill              | Purpose          |
| ------------------ | ---------------- |
| `/init`            | CLAUDE.md 초기화 |
| `/api-check`       | API 상태 점검    |
| `/docker-check`    | Docker 설정 점검 |
| `/review`          | PR 코드 리뷰     |
| `/security-review` | 보안 감사        |
| `/commit`          | 커밋 자동화      |

## Key Directories

- `src/agents/` - LangGraph 에이전트 (news, viral, social)
- `src/core/` - State, Config, Logging, Refine, Checkpoint
- `src/api/` - FastAPI routes, schemas, services
- `src/infrastructure/` - Cache, Retry, Rate Limiter, Storage, Monitoring
- `src/integrations/` - LLM, MCP, Retrieval, Social
- `apps/web/` - React 프론트엔드
- `config/` - YAML, Prometheus, MCP 설정
- `tests/` - unit/, integration/
- `.github/workflows/` - CI/CD 파이프라인 (5개)
