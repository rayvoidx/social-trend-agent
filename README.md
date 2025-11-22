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
│  │  summarize → report                  │      │
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
- API 키 (OpenAI/Anthropic/Google + 데이터 소스)

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

필수 환경 변수:

```env
# LLM Provider (하나 선택)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# 데이터 소스
BRAVE_API_KEY=...              # MCP를 통한 뉴스/웹 검색
SUPADATA_API_KEY=...           # TikTok/YouTube/X 자막

# 선택사항
YOUTUBE_API_KEY=...            # YouTube Data API
PINECONE_API_KEY=...           # Vector store
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

**데이터 소스**: Brave Search API, NewsAPI, 네이버 뉴스

**출력**: 감성 비율, 빈도 포함 키워드, LLM 생성 인사이트

### Viral Video Agent

조회수/참여도 급증 감지를 통해 바이럴 콘텐츠 패턴을 탐지합니다.

```bash
python main.py --agent viral_video_agent \
  --query "K-pop" \
  --market KR
```

**데이터 소스**: YouTube Data API, Supadata MCP (자막)

**출력**: 급증 감지, 성공 요인, 토픽 클러스터

### Social Trend Agent

여러 플랫폼의 소셜 대화를 모니터링합니다.

```bash
python main.py --agent social_trend_agent \
  --query "브랜드명" \
  --sources x instagram naver_blog
```

**데이터 소스**: X (Twitter), Instagram, 네이버 블로그, RSS

**출력**: 소비자 목소리, 인플루언서 식별, 참여 통계

## 프로젝트 구조

```
src/
├── agents/                    # 에이전트 구현
│   ├── news_trend/           # 뉴스 분석
│   │   ├── graph.py          # LangGraph StateGraph
│   │   ├── tools.py          # 데이터 수집 및 분석
│   │   └── prompts.py        # 시스템 프롬프트
│   ├── viral_video/          # 영상 트렌드 감지
│   └── social_trend/         # 소셜 모니터링
├── api/                      # FastAPI 서버
│   └── routes/
│       ├── dashboard.py      # 메인 API 라우트
│       └── n8n.py            # 웹훅 연동
├── core/                     # 핵심 유틸리티
│   ├── state.py              # Pydantic 상태 모델
│   ├── config.py             # 설정 관리
│   ├── errors.py             # 에러 처리 및 부분 결과
│   └── logging.py            # 구조화된 로깅
├── infrastructure/           # 프로덕션 인프라
│   ├── cache.py              # TTL 기반 캐싱
│   ├── retry.py              # 지수 백오프
│   ├── distributed.py        # 태스크 큐 및 워커
│   └── monitoring/           # Prometheus 메트릭
├── integrations/             # 외부 서비스
│   ├── llm/                  # 멀티 프로바이더 LLM 클라이언트
│   ├── mcp/                  # MCP 서버 (Brave, Supadata)
│   ├── retrieval/            # Vector 스토어 (Pinecone)
│   └── social/               # 플랫폼 클라이언트
└── domain/                   # 비즈니스 모델

apps/web/                     # React 프론트엔드
config/                       # YAML 설정
artifacts/                    # 생성된 리포트
```

## API

### 엔드포인트

| 메소드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/tasks` | 분석 태스크 제출 |
| GET | `/api/tasks/{id}` | 태스크 상태/결과 조회 |
| GET | `/api/health` | 헬스 체크 |
| WS | `/ws/metrics` | 실시간 메트릭 |

### 예시

```bash
# 태스크 제출
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "news_trend_agent",
    "query": "AI 트렌드",
    "params": {"time_window": "7d"}
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
agents:
  news_trend_agent:
    timeout_seconds: 0          # 타임아웃 없음 (무제한)
    max_concurrent_tasks: 10
    llm:
      provider: openai
      model_name: gpt-4o
      temperature: 0.5
    embedding:
      provider: openai
      model_name: text-embedding-3-large
    vector_store:
      type: pinecone
      index_name: news-trend-index

  viral_video_agent:
    llm:
      provider: google
      model_name: gemini-1.5-pro

  social_trend_agent:
    llm:
      provider: anthropic
      model_name: claude-3-5-sonnet-20241022
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
      "args": ["-y", "@supadata/mcp"],
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
| `LLM_PROVIDER` | Yes | openai, anthropic, google, ollama |
| `OPENAI_API_KEY` | OpenAI 사용시 | OpenAI API 키 |
| `ANTHROPIC_API_KEY` | Anthropic 사용시 | Claude API 키 |
| `GOOGLE_API_KEY` | Google 사용시 | Gemini API 키 |
| `BRAVE_API_KEY` | 권장 | 뉴스/웹 검색 |
| `SUPADATA_API_KEY` | 권장 | MCP를 통한 SNS 데이터 |
| `YOUTUBE_API_KEY` | 선택 | YouTube Data API |
| `PINECONE_API_KEY` | 선택 | Vector store |
| `DATABASE_URL` | 선택 | PostgreSQL |
| `REDIS_URL` | 선택 | Cache |

## 기능

### 멀티 프로바이더 LLM

```python
from src.integrations.llm import get_llm_client

# config/default.yaml에서 자동 로드
llm = get_llm_client(agent_name="news_trend_agent")
response = llm.invoke(prompt)
embeddings = llm.get_embeddings_batch(texts)
```

**지원**: OpenAI, Anthropic, Google Gemini, Azure OpenAI, Ollama

### 우아한 저하 (Graceful Degradation)

```python
from src.core.errors import safe_api_call, PartialResult

# API 실패 시에도 부분 결과로 계속 진행
result = PartialResult()
items = safe_api_call(
    "fetch_news",
    fetch_function,
    fallback_value=[],
    result_container=result
)
```

### 캐싱 및 재시도

```python
from src.infrastructure.cache import cached
from src.infrastructure.retry import backoff_retry

@cached(ttl=3600)
@backoff_retry(max_retries=3, backoff_base=2.0)
def expensive_operation():
    ...
```

### 분산 실행

```python
from src.infrastructure.distributed import DistributedAgentExecutor

executor = DistributedAgentExecutor(num_workers=4)
task_id = await executor.submit_task(
    agent_name="news_trend_agent",
    query="AI",
    priority=TaskPriority.HIGH
)
result = await executor.wait_for_result(task_id)
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
```

## 개발

### 테스트

```bash
# 유닛 테스트
pytest tests/unit/ -v

# 통합 테스트
pytest tests/integration/ -v

# 특정 테스트
pytest tests/unit/test_mcp_servers.py -v
```

### 프론트엔드

```bash
cd apps/web
npm install
npm run dev
# http://localhost:5173
```

## 배포

### Docker

```bash
# 이미지 빌드
docker build -t social-trend-agent .

# 컨테이너 실행
docker run -p 8000:8000 --env-file .env social-trend-agent
```

### Docker Compose

전체 스택 (API + Redis + 모니터링):

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
| `redis` | 6379 | 캐시 및 세션 스토리지 |
| `prometheus` | 9090 | 메트릭 수집 |

#### 환경 변수 설정

`.env` 파일 생성:

```env
# 필수
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
BRAVE_API_KEY=...
SUPADATA_API_KEY=...

# 선택
REDIS_URL=redis://redis:6379
DATABASE_URL=postgresql://user:pass@db:5432/trends
```

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
| 프레임워크 | FastAPI 0.115, LangGraph 0.2 |
| LLM | OpenAI, Anthropic, Google Gemini |
| 임베딩 | OpenAI, Voyage AI |
| Vector DB | Pinecone |
| MCP | Brave Search, Supadata |
| 캐시 | In-memory, Redis |
| 프론트엔드 | React 19, Vite, TailwindCSS |
| 모니터링 | Prometheus |

## 라이선스

MIT

## 기여

1. 저장소 Fork
2. Feature 브랜치 생성
3. 변경사항 커밋
4. 브랜치에 Push
5. Pull Request 생성
