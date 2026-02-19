# Social Trend Agent - 프로젝트 기술 보고서

**프로덕션 레디 멀티 에이전트 AI 시스템**

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [핵심 기술 스택](#4-핵심-기술-스택)
5. [에이전트 시스템 상세](#5-에이전트-시스템-상세)
6. [코드 로직 분석](#6-코드-로직-분석)
7. [인프라 및 배포](#7-인프라-및-배포)
8. [API 설계](#8-api-설계)
9. [프론트엔드 구현](#9-프론트엔드-구현)
10. [품질 보증 및 테스트](#10-품질-보증-및-테스트)
11. [핵심 설계 패턴](#11-핵심-설계-패턴)
12. [성능 최적화 전략](#12-성능-최적화-전략)
13. [기술적 차별점](#13-기술적-차별점)

---

## 1. 프로젝트 개요

### 1.1 프로젝트 소개

Social Trend Agent는 **LangGraph 기반의 프로덕션 레디 멀티 에이전트 AI 시스템**으로, 뉴스, 영상, 소셜 미디어 전반의 트렌드 분석을 자동화합니다.

### 1.2 핵심 가치

| 항목                   | 설명                                                 |
| ---------------------- | ---------------------------------------------------- |
| **자동화된 인사이트**  | 다양한 데이터 소스에서 실시간 트렌드를 수집하고 분석 |
| **멀티 에이전트 협업** | 3개의 독립 에이전트가 협업하여 종합적인 분석 제공    |
| **프로덕션 레디**      | 분산 실행, 캐싱, 모니터링 등 엔터프라이즈급 인프라   |
| **비용 효율성**        | Compound AI 패턴으로 역할별 최적 모델 라우팅         |

### 1.3 기술적 목표

- **Agentic Workflow 적용**: LangGraph 상태 머신 기반 자율 에이전트
- **성능 20% 향상**: 캐싱, 병렬 처리, 레이트 제한으로 최적화
- **테스트 커버리지 80%+**: 단위/통합 테스트 자동화

---

## 2. 시스템 아키텍처

### 2.1 고수준 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                        React Dashboard (:5173)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ AnalysisForm │  │  ResultCard  │  │    McpToolsPanel         │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Server (:8000)                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    REST API Layer                             │   │
│  │  /api/tasks  /api/insights  /api/metrics  /ws/metrics        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                │                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Distributed Agent Executor                       │   │
│  │    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │   │
│  │    │ Worker-1 │  │ Worker-2 │  │ Worker-3 │  │ Worker-4 │   │   │
│  │    └──────────┘  └──────────┘  └──────────┘  └──────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                │                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   Orchestrator (3-Gear)                       │   │
│  │  ┌────────┐    ┌─────────┐    ┌────────────────────────┐     │   │
│  │  │ Router │ -> │ Planner │ -> │     Agent Workers      │     │   │
│  │  │ (gpt-  │    │  (o3)   │    │  news / viral / social │     │   │
│  │  │  mini) │    │         │    │                        │     │   │
│  │  └────────┘    └─────────┘    └────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐      ┌───────────────┐
│  News Trend   │     │ Viral Video   │      │ Social Trend  │
│    Agent      │     │    Agent      │      │    Agent      │
│  (LangGraph)  │     │  (LangGraph)  │      │  (LangGraph)  │
└───────────────┘     └───────────────┘      └───────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Integration Layer                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │   MCP    │  │   LLM    │  │  Vector  │  │      Cache       │    │
│  │ Servers  │  │  Client  │  │  Store   │  │ (Redis/Memory)   │    │
│  │ (Brave,  │  │ (OpenAI, │  │(Pinecone)│  │                  │    │
│  │Supadata) │  │Anthropic)│  │          │  │                  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 데이터 플로우

```
┌─────────┐   ┌─────────┐   ┌───────────┐   ┌─────────┐   ┌────────┐
│ Collect │ → │Normalize│ → │  Analyze  │ → │Summarize│ → │ Report │
│         │   │         │   │           │   │         │   │        │
│ MCP/API │   │ Schema  │   │ Sentiment │   │  LLM    │   │   MD   │
│ 데이터   │   │  변환   │   │ Keywords  │   │ 요약    │   │ 생성   │
└─────────┘   └─────────┘   └───────────┘   └─────────┘   └────────┘
     │                            │
     ▼                            ▼
┌─────────┐                ┌───────────┐
│   RAG   │                │ Guardrail │
│ 검색    │                │ PII/안전  │
└─────────┘                └───────────┘
```

### 2.3 Compound AI 모델 라우팅

```
┌────────────────────────────────────────────────────────────────────┐
│                     Model Role Routing                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Query → [Router: gpt-5-mini] → Complexity Assessment               │
│                 │                                                    │
│                 ├─ Low Complexity ──→ [Cheap Path]                  │
│                 │                       └─ Single Agent             │
│                 │                                                    │
│                 └─ High Complexity ─→ [Planner: o3]                 │
│                                         │                            │
│                                         ▼                            │
│                           ┌─────────────────────────┐               │
│                           │    Structured DAG       │               │
│                           │    (JSON Plan)          │               │
│                           └─────────────────────────┘               │
│                                         │                            │
│                                         ▼                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Worker Execution                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │   │
│  │  │ Collect  │  │ Analyze  │  │Summarize │  │  Report  │    │   │
│  │  │ (tool)   │  │(gpt-mini)│  │(gpt-5.2) │  │ (writer) │    │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. 프로젝트 구조

### 3.1 전체 디렉토리 구조

```
social-trend-agent/
├── src/                           # 메인 애플리케이션 코드
│   ├── agents/                    # 에이전트 구현
│   │   ├── news_trend/            # 뉴스 트렌드 분석 에이전트
│   │   │   ├── graph.py           # LangGraph StateGraph 정의
│   │   │   ├── graph_advanced.py  # 고급 그래프 (루프/병렬/조건)
│   │   │   ├── tools.py           # 데이터 수집/분석 도구
│   │   │   └── prompts.py         # 시스템 프롬프트
│   │   ├── viral_video/           # 바이럴 영상 감지 에이전트
│   │   ├── social_trend/          # SNS 트렌드 모니터링 에이전트
│   │   └── orchestrator.py        # 3-Gear 오케스트레이터
│   │
│   ├── api/                       # FastAPI REST API
│   │   ├── routes/
│   │   │   ├── dashboard.py       # 메인 API 엔드포인트
│   │   │   ├── mcp_routes.py      # MCP 도구 직접 호출
│   │   │   ├── n8n.py             # N8N 웹훅 연동
│   │   │   └── auth_router.py     # 인증 라우터
│   │   ├── services/              # 비즈니스 로직
│   │   └── schemas/               # Pydantic 요청/응답 모델
│   │
│   ├── core/                      # 핵심 유틸리티
│   │   ├── state.py               # AgentState (Pydantic 모델)
│   │   ├── config.py              # ConfigManager (설정 관리)
│   │   ├── errors.py              # PartialResult, 에러 처리
│   │   ├── logging.py             # 구조화된 JSON 로깅
│   │   ├── refine.py              # Self-Refinement 엔진
│   │   ├── checkpoint.py          # Human-in-the-Loop 지원
│   │   ├── routing.py             # 쿼리 라우팅 (ModelRole)
│   │   ├── gateway.py             # API 게이트웨이
│   │   └── planning/              # 계획 수립 모듈
│   │
│   ├── infrastructure/            # 프로덕션 인프라
│   │   ├── cache.py               # TTL 기반 캐싱
│   │   ├── retry.py               # 지수 백오프 재시도
│   │   ├── rate_limiter.py        # Token bucket 알고리즘
│   │   ├── distributed.py         # 분산 태스크 실행
│   │   ├── session_manager.py     # 세션 관리
│   │   ├── storage/               # PostgreSQL, Redis
│   │   └── monitoring/            # Prometheus 메트릭
│   │
│   ├── integrations/              # 외부 서비스 연동
│   │   ├── llm/                   # 멀티 LLM 클라이언트
│   │   │   ├── llm_client.py      # 통합 LLM 인터페이스
│   │   │   ├── analysis_tools.py  # LLM 분석 도구
│   │   │   └── structured_output.py
│   │   ├── mcp/                   # Model Context Protocol
│   │   │   ├── mcp_manager.py     # MCP 서버 관리
│   │   │   ├── news_collect.py    # 뉴스 수집
│   │   │   └── sns_collect.py     # SNS 수집
│   │   ├── retrieval/             # RAG (Vector + Keyword)
│   │   │   ├── rag.py             # 하이브리드 검색
│   │   │   └── vectorstore_pinecone.py
│   │   └── social/                # 플랫폼 클라이언트
│   │
│   └── domain/                    # 비즈니스 도메인
│       ├── models.py              # Insight, Mission, Creator
│       └── mission.py             # 미션 생성/추천
│
├── apps/                          # 멀티 앱 구조
│   └── web/                       # React 프론트엔드
│       ├── src/
│       │   ├── components/        # React 컴포넌트
│       │   ├── api/               # API 클라이언트
│       │   └── types/             # TypeScript 타입
│       └── package.json
│
├── config/                        # 설정 파일
│   ├── default.yaml               # 에이전트별 LLM/모델 설정
│   └── prometheus.yml             # Prometheus 스크래핑
│
├── tests/                         # 자동화 테스트
│   ├── unit/                      # 단위 테스트
│   └── integration/               # 통합 테스트
│
├── docker-compose.yaml            # 전체 스택 조정
├── Dockerfile                     # 멀티 스테이지 빌드
├── pyproject.toml                 # Python 프로젝트 설정
└── main.py                        # 메인 엔트리 포인트
```

### 3.2 모듈 의존성 다이어그램

```
                    ┌─────────────┐
                    │   main.py   │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
│  api/dashboard  │ │ agents/*     │ │ infrastructure/ │
└────────┬────────┘ └──────┬───────┘ └────────┬────────┘
         │                 │                   │
         └─────────────────┼───────────────────┘
                           ▼
                    ┌──────────────┐
                    │    core/     │
                    │ state/config │
                    │ errors/log   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ integrations/│
                    │  llm/mcp/rag │
                    └──────────────┘
```

---

## 4. 핵심 기술 스택

### 4.1 백엔드 기술

| 레이어            | 기술      | 버전    | 용도                    |
| ----------------- | --------- | ------- | ----------------------- |
| **Web Framework** | FastAPI   | 0.115.7 | 비동기 REST API         |
| **ASGI Server**   | Uvicorn   | 0.35.0  | 고성능 ASGI 서버        |
| **Validation**    | Pydantic  | 2.11.7  | 데이터 검증 및 직렬화   |
| **Orchestration** | LangGraph | 0.2.0   | 상태 머신 기반 에이전트 |
| **AI Framework**  | LangChain | 0.3.26  | LLM 통합 프레임워크     |

### 4.2 LLM 프로바이더

| 프로바이더    | 모델              | 역할               |
| ------------- | ----------------- | ------------------ |
| **OpenAI**    | GPT-5.2           | 기본 Writer, 분석  |
| **OpenAI**    | GPT-5-mini        | Router, Tool 호출  |
| **OpenAI**    | o3                | Planner (System-2) |
| **Anthropic** | Claude Sonnet 4.5 | Social Agent 메인  |
| **Google**    | Gemini 2.5 Pro    | Video Agent 메인   |
| **Ollama**    | Local Models      | 로컬 개발/테스트   |

### 4.3 데이터 및 인프라

| 컴포넌트       | 기술       | 용도                  |
| -------------- | ---------- | --------------------- |
| **Vector DB**  | Pinecone   | 의미 기반 검색 (RAG)  |
| **Cache**      | Redis 7    | 세션, API 응답 캐싱   |
| **Monitoring** | Prometheus | 메트릭 수집           |
| **Container**  | Docker     | 컨테이너화            |
| **Protocol**   | MCP        | 외부 데이터 소스 연동 |

### 4.4 프론트엔드 기술

| 기술            | 버전    | 용도             |
| --------------- | ------- | ---------------- |
| **React**       | 19.2.0  | UI 라이브러리    |
| **TypeScript**  | 5.9.3   | 정적 타입        |
| **Vite**        | 5.4.21  | 빌드 도구        |
| **TailwindCSS** | 3.4.18  | 스타일링         |
| **React Query** | 5.90.10 | 데이터 페칭/캐싱 |
| **Recharts**    | 2.12.7  | 차트 시각화      |

---

## 5. 에이전트 시스템 상세

### 5.1 에이전트 개요

```
┌──────────────────────────────────────────────────────────────────────┐
│                         3 Independent Agents                          │
├──────────────────┬───────────────────┬───────────────────────────────┤
│  News Trend      │  Viral Video      │  Social Trend                 │
│  Agent           │  Agent            │  Agent                        │
├──────────────────┼───────────────────┼───────────────────────────────┤
│ LLM: OpenAI      │ LLM: Google       │ LLM: Anthropic                │
│ GPT-5.2          │ Gemini 2.5 Pro    │ Claude Sonnet 4.5             │
├──────────────────┼───────────────────┼───────────────────────────────┤
│ 소스:            │ 소스:             │ 소스:                         │
│ - Brave Search   │ - YouTube API     │ - X/Twitter                   │
│ - NewsAPI        │ - Supadata MCP    │ - Instagram                   │
│ - 네이버 뉴스    │   (자막 추출)     │ - 네이버 블로그               │
├──────────────────┼───────────────────┼───────────────────────────────┤
│ 출력:            │ 출력:             │ 출력:                         │
│ - 감성 분포      │ - 급증 감지       │ - 소비자 목소리               │
│ - 키워드 빈도    │ - 성공 요인       │ - 인플루언서 식별             │
│ - LLM 인사이트   │ - 토픽 클러스터   │ - 참여 통계                   │
└──────────────────┴───────────────────┴───────────────────────────────┘
```

### 5.2 News Trend Agent 상세

#### LangGraph StateGraph 정의

```python
# src/agents/news_trend/graph.py

from langgraph.graph import StateGraph, END
from src.core.state import NewsAgentState

def build_graph(checkpointer=None):
    graph = StateGraph(NewsAgentState)

    # 노드 추가
    graph.add_node("router", router_node)      # 라우팅 결정
    graph.add_node("collect", collect_node)    # 데이터 수집
    graph.add_node("plan", plan_node)          # 실행 계획
    graph.add_node("normalize", normalize_node) # 정규화
    graph.add_node("analyze", analyze_node)    # 감성/키워드 분석
    graph.add_node("summarize", summarize_node) # LLM 요약
    graph.add_node("critic", critic_node)      # 품질 검토
    graph.add_node("report", report_node)      # 리포트 생성
    graph.add_node("notify", notify_node)      # 알림 발송

    # 엣지 정의
    graph.set_entry_point("router")
    graph.add_edge("router", "collect")
    graph.add_edge("collect", "plan")
    graph.add_edge("plan", "normalize")
    graph.add_edge("normalize", "analyze")
    graph.add_edge("analyze", "summarize")
    graph.add_edge("summarize", "critic")
    graph.add_edge("critic", "report")
    graph.add_edge("report", "notify")
    graph.add_edge("notify", END)

    # HITL 지원 (report 전 일시 정지)
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["report"] if checkpointer else None
    )
```

#### 실행 플로우

```
┌────────┐   ┌─────────┐   ┌──────┐   ┌───────────┐   ┌─────────┐
│ Router │ → │ Collect │ → │ Plan │ → │ Normalize │ → │ Analyze │
└────────┘   └─────────┘   └──────┘   └───────────┘   └─────────┘
                                                            │
┌────────┐   ┌────────┐   ┌────────┐   ┌───────────┐        │
│ Notify │ ← │ Report │ ← │ Critic │ ← │ Summarize │ ←──────┘
└────────┘   └────────┘   └────────┘   └───────────┘
                  ▲
                  │ (HITL: 사용자 승인 대기)
```

### 5.3 Orchestrator (3-Gear System)

```python
# src/agents/orchestrator.py

def orchestrate_request(query, agent_hint=None, time_window=None, language=None):
    """
    3-Gear 오케스트레이션:
    1) Cheap Router: 빠른 쿼리 분석 및 복잡도 판단
    2) System-2 Planner: 복잡한 태스크를 위한 DAG 계획 생성
    3) Worker Agents: 선택된 에이전트 실행
    """
    # Gear 1: 라우팅
    routing = route_request("orchestrator", query=query, ...)
    complexity = routing.get("complexity", "medium")

    if complexity == "high":
        # Gear 2: 플래너 호출 (JSON DAG 생성)
        plan = plan_workflow(query, routing, ...)
    else:
        # 단순 쿼리: 단일 에이전트
        primary, _ = select_agent(query, hint=agent_hint, ...)
        plan = {"primary_agent": primary, "agents": [...], "combine": "single"}

    # Gear 3: 워커 실행 정보 반환
    return {"routing": routing, "plan": plan}
```

#### DAG 계획 구조

```json
{
  "primary_agent": "news_trend_agent",
  "agents": [
    {
      "agent_name": "news_trend_agent",
      "params": {"rag_mode": "graph", "rag_top_k": 10},
      "steps": [
        {
          "id": "s1",
          "op": "collect",
          "inputs": [],
          "outputs": ["raw_items"],
          "depends_on": [],
          "retry_policy": {"max_retries": 2, "backoff_seconds": 1.0, "jitter": true},
          "timeout_seconds": 30,
          "circuit_breaker": {"failure_threshold": 2, "reset_seconds": 60}
        },
        {
          "id": "s2",
          "op": "normalize",
          "inputs": ["raw_items"],
          "outputs": ["normalized"],
          "depends_on": ["s1"]
        },
        ...
      ]
    }
  ],
  "combine": "single",
  "notes": "planner_output"
}
```

---

## 6. 코드 로직 분석

### 6.1 설정 관리 시스템

```python
# src/core/config.py

class ConfigManager:
    """
    중앙 집중식 설정 관리자

    특징:
    - 계층적 설정 (defaults → environment → overrides)
    - 환경별 설정 (dev, staging, prod)
    - 핫 리로드 지원
    - 환경 변수 확장 (${VAR:-default})
    """

    def __init__(self, config_dir="config", environment=None):
        self.config_dir = Path(config_dir)
        self.environment = environment or self._detect_environment()

        # 설정 파일 경로
        self.default_config_path = self.config_dir / "default.yaml"
        self.env_config_path = self.config_dir / f"{self.environment.value}.yaml"
        self.override_config_path = self.config_dir / "override.yaml"

        self.reload()

    def reload(self):
        """설정 리로드 (Deep Merge)"""
        config_data = self._load_default_config()
        env_config = self._load_file(self.env_config_path)
        if env_config:
            config_data = self._deep_merge(config_data, env_config)

        # Pydantic으로 검증
        self.config = SystemConfig(**config_data)
```

#### 설정 모델 (Pydantic)

```python
class AgentConfig(BaseModel):
    name: str
    enabled: bool = True
    max_concurrent_tasks: int = Field(default=5, gt=0)
    timeout_seconds: int = Field(default=300, gt=0)
    retry_config: RetryConfig = Field(default_factory=RetryConfig)
    cache_config: CacheConfig = Field(default_factory=CacheConfig)
    llm: Optional[LLMConfig] = None
    embedding: Optional[Dict[str, Any]] = None
    vector_store: Optional[Dict[str, Any]] = None
    # Compound AI: 역할별 모델 라우팅
    model_roles: Optional[Dict[str, str]] = None
```

### 6.2 멀티 LLM 클라이언트

```python
# src/integrations/llm/llm_client.py

class LLMClient:
    """
    통합 LLM 클라이언트

    지원 프로바이더:
    - OpenAI (GPT-5.2, o3)
    - Anthropic (Claude Sonnet 4.5)
    - Google (Gemini 2.5 Pro)
    - Azure OpenAI
    - Groq
    - Ollama (Local)
    """

    def __init__(self, provider=None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "openai")
        self._initialize_client()

    def chat(self, messages, temperature=0.7, max_tokens=2000, json_mode=False):
        """프로바이더별 추상화된 채팅 인터페이스"""
        if self.provider in ["openai", "azure", "groq", "ollama"]:
            return self._chat_openai_compatible(messages, ...)
        elif self.provider == "anthropic":
            return self._chat_anthropic(messages, ...)
        elif self.provider == "google":
            return self._chat_google(messages, ...)

    def chat_json(self, messages, schema=None, temperature=0.3):
        """JSON 구조화 응답"""
        if schema:
            # 스키마 프롬프트 주입
            schema_instruction = f"Respond with JSON: {json.dumps(schema)}"
            messages[-1]["content"] += schema_instruction

        response = self.chat(messages, json_mode=True, ...)
        return json.loads(response)

    def get_embeddings_batch(self, texts, batch_size=100):
        """배치 임베딩 생성"""
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            response = self._client.embeddings.create(model=model, input=batch)
            embeddings.extend([item.embedding for item in response.data])
        return embeddings
```

### 6.3 분산 실행 시스템

```python
# src/infrastructure/distributed.py

class DistributedAgentExecutor:
    """
    분산 에이전트 실행 시스템

    아키텍처:
        Producer → Task Queue → Worker Pool → Results

    특징:
    - 비동기 태스크 큐
    - 워커 풀 관리 (동적 스케일링)
    - 우선순위 기반 스케줄링
    - 장애 복구 및 재시도
    """

    def __init__(self, num_workers=4, agent_executor=None, task_queue=None):
        self.num_workers = num_workers
        self.agent_executor = agent_executor or self._default_executor
        self.task_queue = task_queue or InMemoryTaskQueue()
        self.workers = []
        self.worker_tasks = []

    async def start(self):
        """워커 풀 시작"""
        for i in range(self.num_workers):
            worker = AgentWorker(f"worker-{i}", self.task_queue, self.agent_executor)
            self.workers.append(worker)
            task = asyncio.create_task(worker.start())
            self.worker_tasks.append(task)

    async def submit_task(self, agent_name, query, params=None, priority=TaskPriority.NORMAL):
        """태스크 제출"""
        task = AgentTask(
            task_id=str(uuid.uuid4()),
            agent_name=agent_name,
            query=query,
            params=params or {},
            priority=priority,
        )
        await self.task_queue.enqueue(task)
        return task.task_id

    async def wait_for_result(self, task_id, timeout=None, poll_interval=0.5):
        """태스크 완료 대기"""
        start_time = time.time()
        while True:
            task = await self.task_queue.get_task(task_id)
            if task.status == TaskStatus.COMPLETED:
                return task.result
            if task.status == TaskStatus.FAILED:
                raise RuntimeError(f"Task failed: {task.error}")
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Task timeout")
            await asyncio.sleep(poll_interval)
```

### 6.4 에러 처리 및 Graceful Degradation

```python
# src/core/errors.py

class CompletionStatus(str, Enum):
    FULL = "full"       # 완전 성공
    PARTIAL = "partial" # 부분 성공
    FAILED = "failed"   # 완전 실패

@dataclass
class PartialResult:
    """부분 성공 처리를 위한 결과 컨테이너"""
    status: CompletionStatus = CompletionStatus.FULL
    items: List[Any] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def record_error(self, error: str):
        self.errors.append(error)
        if self.status == CompletionStatus.FULL:
            self.status = CompletionStatus.PARTIAL

def safe_api_call(
    operation_name: str,
    func: Callable,
    *args,
    fallback_value: Any = None,
    result_container: Optional[PartialResult] = None,
    retry_policy: Optional[Dict] = None,
    timeout_seconds: Optional[int] = None,
    raise_on_fail: bool = False,
    **kwargs
) -> Any:
    """
    안전한 API 호출 래퍼

    - 실패 시 fallback_value 반환
    - result_container에 에러 기록
    - 재시도 정책 적용
    """
    try:
        result = func(*args, **kwargs)
        return result
    except Exception as e:
        if result_container:
            result_container.record_error(f"{operation_name}: {str(e)}")
        if raise_on_fail:
            raise
        return fallback_value
```

---

## 7. 인프라 및 배포

### 7.1 Docker Compose 서비스 구성

```yaml
# docker-compose.yaml

version: "3.8"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - REDIS_URL=redis://redis:6379
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  web:
    build: ./apps/web
    ports:
      - "5173:5173"
    depends_on:
      - api

  redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    command: >
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9091:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=15d"

networks:
  default:
    name: trend-network

volumes:
  redis-data:
  prometheus-data:
```

### 7.2 멀티 스테이지 Dockerfile

```dockerfile
# Dockerfile

# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# 빌드 도구 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# 가상 환경 생성
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NLTK 데이터 다운로드
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# 빌드 산출물 복사
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /root/nltk_data /root/nltk_data
ENV PATH="/opt/venv/bin:$PATH"

# 애플리케이션 코드 복사
COPY . .

# 비-root 사용자
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "src.api.routes.dashboard:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.3 Prometheus 모니터링

```yaml
# config/prometheus.yml

global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "api"
    static_configs:
      - targets: ["api:8000"]
    metrics_path: /metrics
```

---

## 8. API 설계

### 8.1 RESTful 엔드포인트

| 메소드   | 경로                      | 설명              |
| -------- | ------------------------- | ----------------- |
| `GET`    | `/api/health`             | 헬스 체크         |
| `GET`    | `/metrics`                | Prometheus 메트릭 |
| `GET`    | `/api/insights`           | 인사이트 목록     |
| `GET`    | `/api/insights/{id}`      | 인사이트 상세     |
| `GET`    | `/api/metrics`            | 실행기 메트릭     |
| `GET`    | `/api/tasks`              | 태스크 목록       |
| `GET`    | `/api/tasks/{id}`         | 태스크 상세       |
| `POST`   | `/api/tasks`              | 태스크 제출       |
| `POST`   | `/api/tasks/batch`        | 일괄 태스크 제출  |
| `DELETE` | `/api/tasks/{id}`         | 태스크 취소       |
| `GET`    | `/api/statistics`         | 집계 통계         |
| `GET`    | `/api/workers`            | 워커 정보         |
| `POST`   | `/api/missions/recommend` | 미션 추천         |
| `GET`    | `/api/dashboard/summary`  | 대시보드 요약     |
| `WS`     | `/ws/metrics`             | 실시간 메트릭     |

### 8.2 요청/응답 스키마

```python
# 태스크 제출 요청
class TaskSubmitRequest(BaseModel):
    agent_name: str = Field(default="auto")  # auto | news_trend_agent | ...
    query: str = Field(...)
    params: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=1, ge=0, le=3)

# 태스크 응답
class TaskResponse(BaseModel):
    task_id: str
    agent_name: str
    query: str
    status: str  # pending | running | completed | failed
    created_at: float
    started_at: Optional[float]
    completed_at: Optional[float]
    duration: Optional[float]
    result: Optional[Dict[str, Any]]
    error: Optional[str]

# 메트릭 응답
class MetricsResponse(BaseModel):
    timestamp: float
    executor_stats: Dict[str, Any]
    recent_tasks: List[Dict[str, Any]]
    performance_summary: Dict[str, Any]
```

### 8.3 WebSocket 실시간 스트리밍

```python
@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """실시간 메트릭 스트리밍 (2초 간격)"""
    await websocket.accept()

    try:
        while True:
            if executor:
                stats = await executor.get_statistics()
                recent_tasks = await executor.task_queue.get_all_tasks()

                await websocket.send_json({
                    "timestamp": datetime.now().timestamp(),
                    "stats": stats,
                    "recent_tasks": [t.to_dict() for t in recent_tasks[:5]],
                })

            await asyncio.sleep(2)
    except Exception:
        pass
    finally:
        await websocket.close()
```

---

## 9. 프론트엔드 구현

### 9.1 컴포넌트 구조

```
apps/web/src/
├── components/
│   ├── Dashboard.tsx        # 메인 대시보드 컨테이너
│   ├── AnalysisForm.tsx     # 분석 요청 폼
│   ├── ResultCard.tsx       # 결과 카드
│   ├── McpToolsPanel.tsx    # MCP 도구 패널
│   ├── Header.tsx           # 헤더
│   └── MissionRecommendations.tsx  # 미션 추천
├── api/
│   ├── client.ts            # FastAPI 클라이언트
│   └── nodeClient.ts        # Node API 클라이언트
├── types/
│   └── index.ts             # TypeScript 타입 정의
├── App.tsx
└── main.tsx
```

### 9.2 Dashboard 컴포넌트

```typescript
// apps/web/src/components/Dashboard.tsx

import { useState } from 'react';
import { AnalysisForm } from './AnalysisForm';
import { ResultCard } from './ResultCard';
import { McpToolsPanel } from './McpToolsPanel';
import api from '../api/client';

export function Dashboard() {
  const [tasks, setTasks] = useState<TaskStatus[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (request: AnalysisRequest) => {
    setIsLoading(true);
    try {
      const { task_id } = await api.submitTask(request);

      // 태스크 목록에 추가
      const newTask: TaskStatus = {
        task_id,
        agent_name: request.agent_type,
        query: request.query,
        status: 'pending',
        created_at: Date.now() / 1000,
      };
      setTasks(prev => [newTask, ...prev]);

      // 폴링 시작
      pollTaskStatus(task_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const pollTaskStatus = async (taskId: string) => {
    const maxAttempts = 60;
    let attempts = 0;

    const poll = async () => {
      const status = await api.getTaskStatus(taskId);
      setTasks(prev => prev.map(t =>
        t.task_id === taskId ? status : t
      ));

      if (status.status === 'pending' || status.status === 'running') {
        if (attempts < maxAttempts) {
          attempts++;
          setTimeout(poll, 2000);
        }
      }
    };

    poll();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 왼쪽: 폼 & MCP 도구 */}
        <div className="lg:col-span-1 space-y-4">
          <AnalysisForm onSubmit={handleSubmit} isLoading={isLoading} />
          <McpToolsPanel />
        </div>

        {/* 오른쪽: 결과 */}
        <div className="lg:col-span-2">
          {tasks.map((task) => (
            <ResultCard key={task.task_id} task={task} />
          ))}
        </div>
      </div>
    </div>
  );
}
```

### 9.3 API 클라이언트

```typescript
// apps/web/src/api/client.ts

import axios from "axios";

const API_BASE_URL = "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export default {
  async submitTask(request: AnalysisRequest): Promise<{ task_id: string }> {
    const { data } = await client.post("/api/tasks", {
      agent_name: request.agent_type,
      query: request.query,
      params: request.params,
      priority: request.priority || 1,
    });
    return data;
  },

  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const { data } = await client.get(`/api/tasks/${taskId}`);
    return data;
  },

  async getInsights(params?: { source?: string; limit?: number }) {
    const { data } = await client.get("/api/insights", { params });
    return data;
  },

  async getStatistics() {
    const { data } = await client.get("/api/statistics");
    return data;
  },
};
```

---

## 10. 품질 보증 및 테스트

### 10.1 테스트 구조

```
tests/
├── unit/                          # 단위 테스트
│   ├── api/
│   │   └── test_auth.py           # 인증 라우터 테스트
│   └── infrastructure/
│       ├── test_cache.py          # TTL 캐싱 테스트
│       └── test_async_redis_cache.py
│
└── integration/                   # 통합 테스트
    ├── test_news_agent_integration.py
    ├── test_social_trend_agent.py
    └── test_api_server.py
```

### 10.2 pytest 설정

```ini
# pytest.ini

[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
```

### 10.3 테스트 실행

```bash
# 모든 테스트
pytest tests/ -v

# 커버리지 리포트
pytest --cov=src tests/ --cov-report=html

# 특정 테스트
pytest tests/integration/test_news_agent_integration.py -v

# 마커별 실행
pytest -m "not slow" tests/
```

### 10.4 CI/CD 파이프라인

```yaml
# .github/workflows/ci.yml

name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run tests
        run: pytest tests/ -v --cov=src

      - name: Lint
        run: |
          pip install ruff black
          ruff check src/
          black --check src/
```

---

## 11. 핵심 설계 패턴

### 11.1 Compound AI (역할 기반 모델 라우팅)

```yaml
# config/default.yaml

agents:
  news_trend_agent:
    model_roles:
      router: gpt-5-mini # 빠른 라우팅 (저비용)
      planner: o3 # 복잡한 계획 (고성능)
      synthesizer: gpt-5-mini # 중간 합성
      writer: gpt-5.2 # 최종 리포트
      sentiment: gpt-5-mini # 감성 분석
      tool: gpt-5-mini # 도구 호출
```

**효과**: 역할에 따라 최적의 모델을 선택하여 비용 효율성 극대화

### 11.2 Graceful Degradation

```python
# 부분 실패 시에도 계속 진행
result = PartialResult(status=CompletionStatus.FULL)

items = safe_api_call(
    "fetch_news",
    fetch_function,
    fallback_value=[],
    result_container=result,
)

# result.status: FULL → PARTIAL (일부 실패 시)
# 분석은 수집된 데이터로 계속 진행
```

### 11.3 Self-Refinement Engine

```python
# src/core/refine.py

class SelfRefineEngine:
    def __init__(self, llm_client, max_iterations=3):
        self.llm_client = llm_client
        self.max_iterations = max_iterations

    def refine(self, content, criteria):
        """품질 기준을 충족할 때까지 반복 개선"""
        for i in range(self.max_iterations):
            evaluation = self._evaluate(content, criteria)
            if evaluation.passed:
                break
            content = self._improve(content, evaluation.feedback)
        return content
```

### 11.4 Human-in-the-Loop (HITL)

```python
# LangGraph 체크포인트 기반 HITL

graph = build_graph(checkpointer=get_checkpointer())

# report 노드 전에 일시 정지
current_state = graph.invoke(initial_state, config=config)

# 사용자 승인 대기
snapshot = graph.get_state(config)
if "report" in snapshot.next:
    choice = input("Proceed? (y/n): ")
    if choice == "y":
        current_state = graph.invoke(None, config=config)  # 재개
```

### 11.5 하이브리드 RAG

```python
# src/integrations/retrieval/rag.py

class RAGSystem:
    def search(self, query, top_k=10, hybrid_alpha=0.7):
        """
        Vector + Keyword 하이브리드 검색

        Args:
            hybrid_alpha: Vector 비중 (1.0 = 순수 Vector, 0.0 = 순수 Keyword)
        """
        vector_results = self._vector_search(query, top_k)
        keyword_results = self._keyword_search(query, top_k)

        # 점수 기반 병합
        return self._merge_results(
            vector_results,
            keyword_results,
            alpha=hybrid_alpha
        )
```

---

## 12. 성능 최적화 전략

### 12.1 캐싱 전략

```python
# TTL 기반 데코레이터 캐싱
@cached(ttl=3600)  # 1시간
def expensive_llm_call(query):
    return llm_client.chat(messages)

# Redis 비동기 캐싱
cache = get_async_cache(prefix="api")

async def list_insights():
    cache_key = "insights:list"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = compute_insights()
    await cache.set(cache_key, result, ttl=300)
    return result
```

### 12.2 재시도 정책

```python
# 지수 백오프 데코레이터
@backoff_retry(max_retries=3, backoff_base=2.0)
async def api_call():
    # 1차 실패: 2초 대기
    # 2차 실패: 4초 대기
    # 3차 실패: 8초 대기
    return await external_api.fetch()
```

### 12.3 레이트 제한

```python
# Token Bucket 알고리즘
class RateLimiter:
    def __init__(self, rate=60, per=60):  # 분당 60회
        self.rate = rate
        self.per = per
        self.tokens = rate
        self.last_update = time.time()

    async def acquire(self):
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / self.per))
        self.last_update = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
```

### 12.4 분산 실행

```python
# 4개 워커 병렬 처리
executor = DistributedAgentExecutor(num_workers=4)

# 우선순위 기반 스케줄링
await executor.submit_task(
    agent_name="news_trend_agent",
    query="긴급 분석",
    priority=TaskPriority.URGENT  # 우선 처리
)
```

---

## 13. 기술적 차별점

### 13.1 핵심 강점

| 영역              | 차별점                                           |
| ----------------- | ------------------------------------------------ |
| **멀티 에이전트** | 3개 독립 에이전트가 LangGraph 상태 머신으로 협업 |
| **Compound AI**   | 역할별 모델 라우팅으로 비용 50%+ 절감 가능       |
| **프로덕션 레디** | 분산 실행, 캐싱, 모니터링, HITL 완비             |
| **확장성**        | Docker Compose로 수평 확장 (scale=N)             |
| **관찰 가능성**   | Prometheus 메트릭, 구조화된 JSON 로깅, Trace ID  |

### 13.2 아키텍처 패턴 요약

```
┌────────────────────────────────────────────────────────────────────┐
│                    적용된 설계 패턴                                  │
├────────────────────────────────────────────────────────────────────┤
│ 1. State Machine Pattern     - LangGraph StateGraph               │
│ 2. Repository Pattern        - Insight/Mission 저장소             │
│ 3. Strategy Pattern          - LLM 프로바이더 전환                 │
│ 4. Decorator Pattern         - @cached, @backoff_retry            │
│ 5. Factory Pattern           - get_llm_client(), get_checkpointer │
│ 6. Singleton Pattern         - ConfigManager, LLMClient           │
│ 7. Observer Pattern          - WebSocket 실시간 메트릭            │
│ 8. Circuit Breaker           - 외부 API 장애 격리                 │
│ 9. Saga Pattern              - 분산 트랜잭션 (Orchestrator)       │
│ 10. CQRS                     - 읽기/쓰기 분리 (API/Worker)        │
└────────────────────────────────────────────────────────────────────┘
```

### 13.3 확장 가능성

| 확장 방향             | 구현 방법                                 |
| --------------------- | ----------------------------------------- |
| **새 에이전트 추가**  | `src/agents/` 하위에 graph.py 추가        |
| **새 LLM 프로바이더** | `llm_client.py`에 `_init_*()` 메서드 추가 |
| **새 데이터 소스**    | MCP 서버 설정 추가                        |
| **새 Vector DB**      | `retrieval/` 하위에 어댑터 추가           |
| **수평 확장**         | `docker-compose up --scale api=N`         |

---

## 부록: 실행 방법

### 로컬 개발

```bash
# 1. 의존성 설치
uv sync  # 또는 pip install -r requirements.txt

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일에 API 키 입력

# 3. CLI 모드 실행
python main.py --agent news_trend_agent --query "AI 트렌드" --window 7d

# 4. Web 모드 실행
python main.py --mode web
# API: http://localhost:8000
# 대시보드: http://localhost:5173
```

### Docker 배포

```bash
# 전체 스택 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f api

# 스케일링
docker-compose up -d --scale api=3
```

---

**작성일**: 2026-02-08
**버전**: 4.0.0
**기술 스택**: FastAPI + LangGraph + React + Redis + Prometheus
**라이선스**: MIT
