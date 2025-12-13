# Social Trend Agent

뉴스, 영상, 소셜 미디어 전반의 자동화된 트렌드 분석을 위한 프로덕션 레디 멀티 에이전트 시스템.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)

## 개요

LangGraph 기반 AI 오케스트레이션 시스템으로, 트렌드 감지 및 분석을 자동화합니다. 다양한 소스에서 데이터를 수집하고, 감성 분석 및 키워드 추출을 수행하며, LLM을 활용하여 실행 가능한 인사이트를 생성합니다.

## 아키텍처

```
┌─────────────────────────────────────────────────┐
│               FastAPI Server (:8000)            │
├─────────────────────────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐     │
│  │   News    │ │   Video   │ │  Social   │     │
│  │   Agent   │ │   Agent   │ │   Agent   │     │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘     │
│        └─────────────┼─────────────┘           │
│                      ▼                          │
│  ┌──────────────────────────────────────┐      │
│  │    LangGraph State Machine           │      │
│  │  collect → normalize → analyze →     │      │
│  │  report → approve (HITL)             │      │
│  └──────────────────────────────────────┘      │
│                      │                          │
│  ┌────────┬──────────┼──────────┬────────┐     │
│  │  MCP   │   LLM    │  Vector  │ Cache  │     │
│  │Servers │  Client  │  Store   │        │     │
│  └────────┴──────────┴──────────┴────────┘     │
└─────────────────────────────────────────────────┘
```

## 빠른 시작

### 필수 요구사항

- Python 3.11+
- API 키 (OpenAI/Anthropic/Google 중 하나 이상 + 데이터 소스)

### 설치

```bash
git clone https://github.com/your-repo/social-trend-agent.git
cd social-trend-agent

# uv로 설치 (권장)
uv sync

# 또는 pip
pip install -r requirements.txt
```

### 환경 설정

```bash
cp .env.example .env
```

필수/권장 환경 변수:

```env
# Core runtime
ENVIRONMENT=development
LLM_PROVIDER=openai              # openai | anthropic | google | azure | ollama

# LLM Keys (하나 이상 필수)
OPENAI_API_KEY=sk-...            # OpenAI 사용 시
ANTHROPIC_API_KEY=sk-ant-...     # Anthropic 사용 시
GOOGLE_API_KEY=...               # Google Gemini 사용 시

# MCP 데이터 소스 (권장)
SUPADATA_API_KEY=...             # SNS 데이터 (X, TikTok, YouTube 자막)
BRAVE_API_KEY=...                # 뉴스/웹 검색

# 선택사항
YOUTUBE_API_KEY=...              # YouTube Data API
PINECONE_API_KEY=...             # Vector store (RAG)
```

### 실행

```bash
# CLI 모드
python main.py --agent news_trend_agent --query "AI 트렌드" --window 7d

# Web 모드 (API + 대시보드)
python main.py --mode web
# API: http://localhost:8000
# 문서: http://localhost:8000/docs
```

## 에이전트

### News Trend Agent

뉴스 보도량, 감성 분포를 분석하고 주요 토픽을 추출합니다.

```bash
python main.py --agent news_trend_agent \
  --query "전기자동차" \
  --window 7d \
  --language ko
```

**데이터 소스**: Brave Search MCP, NewsAPI, 네이버 뉴스

**출력**: 감성 비율, 빈도 포함 키워드, LLM 생성 인사이트

**주요 도구**:
- `search_news()`: MCP 기반 뉴스 검색 (캐싱 지원)
- `analyze_sentiment()`: 감성 분류
- `extract_keywords()`: 키워드 추출 및 빈도 분석
- `summarize_trend()`: LLM 기반 요약
- `retrieve_relevant_items()`: RAG 통합
- `redact_pii()`: 개인정보 보호
- `check_safety()`: 콘텐츠 안전성 검증

### Viral Video Agent

조회수/참여도 급증 감지를 통해 바이럴 콘텐츠 패턴을 탐지합니다.

```bash
python main.py --agent viral_video_agent \
  --query "K-pop" \
  --market KR
```

**데이터 소스**: YouTube Data API, Supadata MCP (자막)

**출력**: 급증 감지, 성공 요인, 토픽 클러스터

**주요 도구**:
- `fetch_video_stats()`: 멀티 플랫폼 영상 메트릭 수집
- `detect_spike()`: Z-score 기반 이상 감지 (임계값: 2.0σ)
- `topic_cluster()`: 영상 카테고리화 및 클러스터링
- `generate_success_factors()`: LLM 기반 패턴 분석

### Social Trend Agent

여러 플랫폼의 소셜 대화를 모니터링합니다.

```bash
python main.py --agent social_trend_agent \
  --query "브랜드명" \
  --sources x instagram naver_blog
```

**데이터 소스**: X (Twitter), Instagram, 네이버 블로그, RSS

**출력**: 소비자 목소리, 인플루언서 식별, 참여 통계

**주요 도구**:
- `fetch_x_posts()`, `fetch_instagram_posts()`, `fetch_naver_blog_posts()`, `fetch_rss_feeds()`
- `normalize_items()`: 통합 스키마 변환
- `analyze_sentiment_and_keywords()`: 감성 및 키워드 분석
- `generate_trend_report()`: 리포트 생성

## 프로젝트 구조

```
src/
├── agents/                    # 에이전트 구현
│   ├── news_trend/           # 뉴스 분석
│   │   ├── graph.py          # LangGraph StateGraph
│   │   ├── graph_advanced.py # 고급 그래프 (루프/병렬/조건)
│   │   ├── tools.py          # 데이터 수집 및 분석
│   │   └── prompts.py        # 시스템 프롬프트
│   ├── viral_video/          # 영상 트렌드 감지
│   ├── social_trend/         # 소셜 모니터링
│   └── orchestrator.py       # 에이전트 오케스트레이터
├── api/                      # FastAPI 서버
│   ├── routes/
│   │   ├── dashboard.py      # 메인 API 라우트
│   │   ├── mcp_routes.py     # MCP 도구 직접 호출
│   │   └── n8n.py            # 웹훅 연동
│   ├── services/             # 비즈니스 로직
│   └── schemas/              # Pydantic 요청/응답 모델
├── core/                     # 핵심 유틸리티
│   ├── state.py              # Pydantic 상태 모델 (AgentState)
│   ├── config.py             # 설정 관리 (멀티 LLM)
│   ├── errors.py             # 에러 처리 및 부분 결과 (PartialResult)
│   ├── logging.py            # 구조화된 로깅 (AgentLogger)
│   ├── refine.py             # Self-refinement 엔진
│   ├── checkpoint.py         # Human-in-the-loop 지원
│   ├── routing.py            # 쿼리 라우팅
│   ├── gateway.py            # API 게이트웨이
│   ├── planning/             # 계획 수립 모듈
│   └── utils.py              # 유틸리티 함수
├── infrastructure/           # 프로덕션 인프라
│   ├── cache.py              # TTL 기반 캐싱 (@cached)
│   ├── retry.py              # 지수 백오프 (@backoff_retry)
│   ├── rate_limiter.py       # Token bucket 알고리즘
│   ├── distributed.py        # 태스크 큐 및 워커
│   ├── session_manager.py    # CLI/API 세션 관리
│   ├── timeout.py            # 타임아웃 처리
│   ├── storage/              # PostgreSQL, Redis
│   ├── monitoring/           # Prometheus 메트릭, 미들웨어
│   └── evaluation/           # 품질 평가
├── integrations/             # 외부 서비스
│   ├── llm/                  # 멀티 프로바이더 LLM 클라이언트
│   │   ├── llm_client.py     # 통합 LLM 인터페이스
│   │   ├── analysis_tools.py # LLM 분석 도구
│   │   └── structured_output.py # Pydantic 스키마 검증
│   ├── mcp/                  # MCP 서버 (Brave, Supadata)
│   │   ├── mcp_manager.py    # MCP 서버 관리
│   │   ├── news_collect.py   # 뉴스 수집
│   │   ├── sns_collect.py    # SNS 수집
│   │   ├── supadata_contract.py # Supadata 계약 정의
│   │   └── mcp_config.json   # MCP 설정
│   ├── retrieval/            # Vector 스토어 (Pinecone)
│   │   ├── rag.py            # 하이브리드 검색 (Vector + Keyword)
│   │   └── vectorstore_pinecone.py
│   └── social/               # 플랫폼 클라이언트 (X, Instagram, TikTok)
└── domain/                   # 비즈니스 모델
    ├── models.py             # Insight, Mission, Creator
    ├── schemas.py            # 공통 스키마
    └── planning/             # 계획 도메인 모델

apps/web/                     # React 프론트엔드
├── src/
│   ├── components/           # Dashboard, AnalysisForm, McpToolsPanel
│   ├── api/                  # API 클라이언트
│   └── types/                # TypeScript 정의
config/                       # YAML 설정
artifacts/                    # 생성된 리포트
tests/                        # 테스트 (unit, integration)
scripts/                      # 유틸리티 스크립트
```

## API

### 엔드포인트

| 메소드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/tasks` | 분석 태스크 제출 |
| GET | `/api/tasks/{id}` | 태스크 상태/결과 조회 |
| GET | `/api/health` | 헬스 체크 |
| GET | `/api/metrics` | 현재 메트릭 |
| GET | `/api/statistics` | 집계 통계 |
| WS | `/ws/metrics` | 실시간 메트릭 스트림 |

### 예시

```bash
# 태스크 제출
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "news_trend_agent",
    "query": "AI 트렌드",
    "params": {"time_window": "7d"},
    "priority": 1
  }'

# 응답
{"task_id": "abc-123", "status": "pending"}

# 결과 조회
curl http://localhost:8000/api/tasks/abc-123
```

## 설정

### 에이전트 설정

`config/default.yaml`:

```yaml
environment: development
debug: true

llm:
  provider: openai
  model_name: gpt-5.2
  temperature: 0.7

agents:
  news_trend_agent:
    timeout_seconds: 300
    max_concurrent_tasks: 10
    # Compound AI: role-based model assignment
    model_roles:
      router: gpt-5-mini
      planner: o3
      synthesizer: gpt-5-mini
      writer: gpt-5.2
      sentiment: gpt-5-mini
      tool: gpt-5-mini
    llm:
      provider: openai
      model_name: gpt-5.2
      temperature: 0.5
    embedding:
      provider: openai
      model_name: text-embedding-3-large
    vector_store:
      type: pinecone
      index_name: news-trend-index

  viral_video_agent:
    model_roles:
      router: gpt-5-mini
      planner: o3
      synthesizer: gpt-5-mini
      writer: gpt-5.2
    llm:
      provider: google
      model_name: gemini-2.5-pro

  social_trend_agent:
    model_roles:
      router: gpt-5-mini
      planner: o3
      synthesizer: gpt-5-mini
      writer: gpt-5.2
    llm:
      provider: anthropic
      model_name: claude-sonnet-4-5
    embedding:
      provider: voyage
      model_name: voyage-3

monitoring:
  enabled: true
  metrics_enabled: true

rate_limit:
  enabled: true
  requests_per_minute: 60
```

### MCP 서버

`src/integrations/mcp/mcp_config.json`:

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {"BRAVE_API_KEY": "${BRAVE_API_KEY}"}
    },
    "supadata-ai-mcp": {
      "command": "npx",
      "args": ["-y", "supadata-mcp"],
      "env": {"SUPADATA_API_KEY": "${SUPADATA_API_KEY}"}
    }
  }
}
```

**Supadata MCP 도구**:
- `supadata_transcript` - 영상 자막 추출 (YouTube, TikTok, Instagram, X)
- `supadata_scrape` - 웹 콘텐츠를 마크다운으로 변환
- `supadata_map` - 웹사이트 URL 매핑
- `supadata_crawl` - 전체 사이트 크롤링

## 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `ENVIRONMENT` | 선택 | 실행 환경 (development/staging/production) |
| `LLM_PROVIDER` | 선택 | 기본 LLM 프로바이더 (openai/anthropic/google/ollama) |
| `OPENAI_API_KEY` | 조건부 | OpenAI 사용 시 API 키 |
| `ANTHROPIC_API_KEY` | 조건부 | Anthropic 사용 시 API 키 |
| `GOOGLE_API_KEY` | 조건부 | Gemini 사용 시 API 키 |
| `SUPADATA_API_KEY` | 권장 | MCP를 통한 SNS 데이터 |
| `SUPADATA_MCP_SERVER` | 선택 | MCP 서버 이름 (기본: supadata-ai-mcp) |
| `BRAVE_API_KEY` | 권장 | 뉴스/웹 검색 |
| `YOUTUBE_API_KEY` | 선택 | YouTube Data API |
| `PINECONE_API_KEY` | 선택 | Vector store |
| `DATABASE_URL` | 선택 | PostgreSQL |
| `REDIS_URL` | 선택 | Cache |
| `SLACK_WEBHOOK_URL` | 선택 | Slack 알림 |
| `N8N_WEBHOOK_URL` | 선택 | N8N 자동화 연동 |

## 기능

### 멀티 프로바이더 LLM

```python
from src.integrations.llm import get_llm_client

# config/default.yaml에서 자동 로드
llm = get_llm_client(agent_name="news_trend_agent")
response = llm.invoke(prompt)
embeddings = llm.get_embeddings_batch(texts)
```

**지원**: OpenAI (GPT-5.2, o3), Anthropic (Claude Sonnet 4.5), Google (Gemini 2.5 Pro), Azure OpenAI, Ollama

### Compound AI (Role-based Model Routing)

```yaml
# config/default.yaml
agents:
  news_trend_agent:
    model_roles:
      router: gpt-5-mini      # 빠른 라우팅 결정
      planner: o3             # 복잡한 계획 수립
      synthesizer: gpt-5-mini # 중간 합성
      writer: gpt-5.2         # 최종 리포트 작성
      sentiment: gpt-5-mini   # 감성 분석
      tool: gpt-5-mini        # 도구 호출
```

비용 효율성을 위해 역할별로 다른 모델을 할당합니다.

### 우아한 저하 (Graceful Degradation)

```python
from src.core.errors import safe_api_call, PartialResult, CompletionStatus

# API 실패 시에도 부분 결과로 계속 진행
result = PartialResult(status=CompletionStatus.FULL)
items = safe_api_call(
    "fetch_news",
    fetch_function,
    fallback_value=[],
    result_container=result
)
# result.status가 PARTIAL 또는 FAILED로 자동 업데이트
```

### Self-Refinement 엔진

```python
from src.core.refine import SelfRefineEngine

engine = SelfRefineEngine(llm_client, max_iterations=3)
result = engine.refine(
    content=initial_report,
    criteria=["factuality", "actionability", "coverage"]
)
# 품질 기준을 충족할 때까지 반복 개선
```

### Human-in-the-Loop

```python
from src.core.checkpoint import CheckpointManager

# LangGraph에서 승인 노드 사용
# approve_node에서 사용자 승인 대기
# 승인 후 report_node로 진행
```

### 캐싱 및 재시도

```python
from src.infrastructure.cache import cached
from src.infrastructure.retry import backoff_retry

@cached(ttl=3600)  # 1시간 캐싱
@backoff_retry(max_retries=3, backoff_base=2.0)  # 지수 백오프
def expensive_operation():
    ...
```

### 분산 실행

```python
from src.infrastructure.distributed import DistributedAgentExecutor, TaskPriority

executor = DistributedAgentExecutor(num_workers=4)
task_id = await executor.submit_task(
    agent_name="news_trend_agent",
    query="AI",
    priority=TaskPriority.HIGH
)
result = await executor.wait_for_result(task_id)
```

### 하이브리드 RAG

```python
from src.integrations.retrieval.rag import RAGSystem

rag = RAGSystem(pinecone_client, embedding_provider)
# Vector + Keyword 하이브리드 검색
results = rag.search(query, top_k=10, hybrid_alpha=0.7)
```

## 출력

리포트는 `artifacts/{agent_name}/{run_id}.md`에 저장됩니다:

```markdown
# 뉴스 트렌드 분석 리포트

## 요약
산업 전반에서 AI 도입이 가속화되고 있습니다...

## 감성 분석
- 긍정: 45%
- 중립: 40%
- 부정: 15%

## 주요 키워드
1. 인공지능 (42)
2. 머신러닝 (28)
3. 자동화 (18)

## 핵심 인사이트
1. 기업 도입 증가
2. 규제 우려 대두

## 권장 조치
1. 경쟁사 AI 계획 모니터링
2. 내부 활용 사례 평가

## 품질 메트릭
- Coverage: 0.85
- Factuality: 0.92
- Actionability: 0.78
```

## 개발

### 테스트

```bash
# 통합 테스트
pytest tests/integration/ -v

# 특정 테스트
pytest tests/integration/test_news_agent_integration.py -v

# 커버리지
pytest --cov=src tests/
```

### 프론트엔드

```bash
cd apps/web
npm install
npm run dev
# http://localhost:5173
```

**기술 스택**: React 19, TypeScript 5, Vite, TailwindCSS

## 배포

### Docker

```bash
# 이미지 빌드
docker build -t social-trend-agent .

# 컨테이너 실행
docker run -p 8000:8000 --env-file .env social-trend-agent
```

### Docker Compose

전체 스택 (API + Web + Redis + 모니터링):

```bash
# 전체 스택 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f api

# 중지
docker-compose down
```

#### 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| `api` | 8000 | FastAPI 메인 서버 |
| `web` | 5173 | React 프론트엔드 |
| `redis` | 6379 | 캐시 및 세션 스토리지 |
| `prometheus` | 9091 | 메트릭 수집 |

#### 프로덕션 배포

```bash
# 프로덕션 모드로 빌드 및 실행
docker-compose -f docker-compose.yaml up -d --build

# 스케일링
docker-compose up -d --scale api=3
```

## 기술 스택

| 컴포넌트 | 기술 |
|----------|------|
| 프레임워크 | FastAPI 0.115, LangGraph 0.2, Uvicorn |
| 언어 | Python 3.11+, TypeScript 5 |
| LLM | OpenAI GPT-5.2/o3, Anthropic Claude Sonnet 4.5, Google Gemini 2.5 Pro, Ollama |
| 임베딩 | OpenAI text-embedding-3-large, Voyage AI voyage-3, Google embedding-001 |
| Vector DB | Pinecone |
| MCP | Brave Search, Supadata |
| 데이터 수집 | NewsAPI, YouTube API, Social Platform APIs |
| 캐시 | In-memory TTL, Redis |
| 프론트엔드 | React 19, Vite, TailwindCSS |
| 모니터링 | Prometheus, 구조화된 JSON 로깅 |
| NLP | NLTK, TextBlob, LangChain |
| 컨테이너 | Docker, Docker Compose |
| DB | PostgreSQL (선택), Redis |

## 핵심 패턴

1. **멀티 에이전트 아키텍처**: LangGraph 상태 머신 기반 독립 에이전트
2. **Compound AI**: 역할별 모델 라우팅으로 비용 최적화 (router/planner/writer)
3. **Graceful Degradation**: `PartialResult`로 부분 성공 처리
4. **Human-in-the-Loop**: 체크포인트 기반 승인 워크플로우
5. **Self-Refinement**: LLM 평가를 통한 품질 개선 루프
6. **멀티 프로바이더 LLM**: OpenAI, Anthropic, Google 동적 라우팅
7. **분산 실행**: 우선순위 기반 태스크 큐
8. **Structured Output**: Pydantic 스키마로 검증된 LLM 응답
9. **하이브리드 RAG**: Vector + Keyword 검색
10. **Observable**: Prometheus 메트릭 + Trace ID 로깅
11. **Rate Limiting**: Token bucket 알고리즘

## 라이선스

MIT

## 기여

1. 저장소 Fork
2. Feature 브랜치 생성
3. 변경사항 커밋
4. 브랜치에 Push
5. Pull Request 생성
