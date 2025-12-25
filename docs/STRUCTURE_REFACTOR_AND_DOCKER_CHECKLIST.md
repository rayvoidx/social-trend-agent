### 목적
이 문서는 `social-trend-agent` 레포를 **운영/배포 친화적 구조**로 정리하기 위한:
- **구조 리팩토링 TODO(단계별, import shim 포함)**
- **Docker 배포 체크리스트**
를 “현재 레포 기준”으로 구체화합니다.

---

### 현재 발견된 구조적 Problems (요약)
- **패키지 오염(package pollution)**: 런타임 산출물이 `src/` 아래에 존재/생성되는 경로가 있었음(예: 레거시 `src/artifacts/`).
- **중복/비정상 경로**: 공백이 포함된 `src/integrations/retrieval 2/` 같은 디렉터리가 존재(유지보수/CI 리스크).
- **핵심 기능 모듈의 분산**: 계획 실행(Plan/DAG) 관련 로직이 `src/core/plan.py`, `src/core/plan_graph.py` 등으로 흩어져 있어 확장/테스트 난이도 증가.
- **운영 경로(import) 안정성 필요**: 폴더 이동 시 import 깨짐 방지를 위해 shim 전략이 필수.

---

### 구조 리팩토링 TODO (단계별, 안전한 import shim 포함)

#### Phase 0 — Safety Net (필수)
- **0.1**: 전역 컴파일 체크(빠른 스모크)
  - `python -m compileall -q src`
- **0.2**: 아티팩트/런타임 출력이 `src/` 아래로 쓰이지 않도록 점검
  - 산출물은 반드시 프로젝트 루트 `artifacts/` 사용
- **0.3**: “중복/쓰레기 디렉터리” 제거
  - 예: `src/integrations/retrieval 2/` (공백 경로)

#### Phase 1 — Core Planning 모듈 정리 (import shim 포함) ✅(진행 대상)
목표: 계획/플랜 실행 관련 모듈을 한 곳으로 모으고, 기존 import를 깨지 않음.

- **1.1**: 신규 패키지 생성
  - `src/core/planning/`
    - `plan.py` (기존 `src/core/plan.py`의 canonical)
    - `graph.py` (기존 `src/core/plan_graph.py`의 canonical)
    - `__init__.py` (re-export)
- **1.2**: 기존 경로는 shim으로 유지
  - `src/core/plan.py` → `from src.core.planning.plan import *`
  - `src/core/plan_graph.py` → `from src.core.planning.graph import *`
- **1.3**: 주요 사용처 import를 새 경로로 전환(선택이지만 권장)
  - `src/agents/*/graph.py` 등에서 `src.core.planning.*`로 import

#### Phase 2 — Domain vs Core 분리 정교화 (중요)
현재 `src/domain/plan.py`(스키마)와 `src/core/planning/*`(실행)가 공존합니다.

- **2.1**: “스키마”는 `domain`, “실행/런너”는 `core`로 고정
  - 스키마: `src/domain/planning/schemas.py` (AgentPlan 등)
  - 실행: `src/core/planning/*`
- **2.2**: 네이밍 충돌 방지
  - `core/planning/plan.py`는 “plan parsing/util”에 집중
  - `domain/plan.py`는 Pydantic 모델에 집중
  - 레거시 호환: `src/domain/plan.py`는 shim으로 유지(re-export)

#### Phase 3 — Runtime outputs / artifacts 정리(운영 필수)
- **3.1**: 레거시 `src/artifacts/` → 루트 `artifacts/`로 마이그레이션
  - 제공 스크립트: `scripts/migrate_src_artifacts.py`
- **3.2**: `src/artifacts/` 디렉터리는 최종적으로 제거(또는 빈 디렉터리만 남김)

#### Phase 4 — 테스트/CI 최소 구성(배포 필수)
- **4.1**: CI에서 최소 스모크 추가
  - `python -m compileall -q src`
  - (가능하면) `pytest -q` 스모크
- **4.2**: Docker build 스모크
  - `docker build .`

---

### Docker 배포 체크리스트 (운영 기준)

#### A) 사전 준비
- **A.1**: `.env` 생성
  - `cp env.template .env`
- **A.2**: 필수 환경 변수
  - `LLM_PROVIDER`, `OPENAI_API_KEY`(또는 provider별 키)
  - MCP: `SUPADATA_API_KEY`, `SUPADATA_MCP_SERVER`, tool names
  - RAG 사용 시: `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`

#### B) 로컬 스모크(배포 전)
- **B.1**: 컴파일 스모크
  - `python -m compileall -q src`
- **B.2**: API 라우트 스모크(서버 실행이 가능한 환경에서)
  - health: `/api/health`
  - metrics: `/metrics`

#### C) Docker 빌드/실행
- **C.1**: 이미지 빌드
  - `docker build -t social-trend-agent:local .`
- **C.2**: compose 실행
  - `docker compose up -d --build`
- **C.3**: 컨테이너 로그 확인
  - `docker compose logs -f`

#### D) 운영 점검
- **D.1**: Task 제출(오케스트레이터 경유)
  - `POST /api/tasks` with `agent_name=auto`
- **D.2**: 관측(Observability)
  - 로그에서 run_id/plan_execution 흐름 확인
  - Circuit breaker / retry 정책이 plan대로 동작하는지 확인

---

### “안 깨지는” 파일 이동 규칙 (import shim 가이드)
- **규칙 1**: 먼저 새 경로에 canonical 구현을 추가한다.
- **규칙 2**: 기존 경로 파일은 삭제하지 말고 “re-export shim”으로 유지한다.
- **규칙 3**: 사용처 import는 점진적으로 새 경로로 옮긴다(한 PR에 다 하지 않음).
- **규칙 4**: 각 단계마다 `compileall`로 스모크한다.


