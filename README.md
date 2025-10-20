# 소비자 트렌드 자동 분석 에이전트 (Monorepo)

> 신제품/기존제품 반응을 **실시간 자동 분석**하여 마케팅·상품기획의 빠른 의사결정을 돕는 **토탈 에이전트 시스템**
> **Agents:** news_trend_agent, viral_video_agent *(+ optional creator_onboarding_agent)*

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![LangChain](https://img.shields.io/badge/LangChain-Latest-green.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-Latest-orange.svg)
![n8n](https://img.shields.io/badge/n8n-Workflow-orange.svg)
![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Compose-informational.svg)

---

## 📋 목차
- [프로젝트 소개](#-프로젝트-소개)
- [Working Principles](#-working-principles)
- [에이전트 레지스트리](#-에이전트-레지스트리)
- [시스템 아키텍처](#-시스템-아키텍처)
- [설치 및 실행](#-설치-및-실행)
- [빠른 검증(POW)](#-빠른-검증pow)
- [환경 변수(.env)](#-환경-변수env)
- [사용 예시](#-사용-예시)
- [커스터마이징](#-커스터마이징)
- [운영·보안](#-운영보안)
- [라이선스](#-라이선스)

---

## 🎯 프로젝트 소개

**"뉴스·SNS·동영상·커뮤니티 전 채널의 트렌드/반응을 자동 수집·분석·요약해, 하루 단위가 아닌 '분 단위'로 전략을 검증·실행하도록 돕습니다."**

### 주요 기능
- **자동 ETL**: News/Naver/YouTube/TikTok(합법적 커넥터)
- **분석**: 감성(긍/부/중), 키워드/토픽, 바이럴 신호(급상승)
- **리포트**: 출처 Top-N 링크, 정량지표, 실행 권고안
- **알림/자동화**: n8n/Slack/Webhook

---

## 🧭 Working Principles

1. **에이전트=핵심 동료**: 사람×AI 협업 전제
2. **토론보다 작동물**: `POW.md` 기반 5~10분 내 검증
3. **내부 효율=제품 가치**: 공통 유틸·워크플로우 재사용

---

## 🗂 에이전트 레지스트리

| Agent | 목적 | 핵심 Tool | 대표 산출물 |
|---|---|---|---|
| `news_trend_agent` | 글로벌/국내 뉴스 트렌드 추적 | `search_news`, `analyze_sentiment`, `extract_keywords`, `summarize_trend` | 일/주간 트렌드 리포트(MD) |
| `viral_video_agent` | 유튜브/틱톡 급상승 탐지 | `fetch_video_stats`, `detect_spike`, `topic_cluster` | 급상승 랭킹 & 성공요인 해설(MD) |
| `creator_onboarding_agent` (선택) | 크리에이터 온보딩 심사 | `profile_enrich`, `brand_safety`, `copyright_risk` | 합격/보류/탈락 + 개선 가이드 |

---

## 🏗 시스템 아키텍처

### 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Entry Points                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Open WebUI  │  │  CLI Runner  │  │  n8n Webhook │              │
│  │  (Frontend)  │  │  (scripts/)  │  │  (Automation)│              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
└─────────┼──────────────────┼──────────────────┼──────────────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │   LangGraph Orchestration Layer     │
          │                                     │
          │  ┌────────────────────────────┐    │
          │  │    StateGraph Pipeline      │    │
          │  │  collect → normalize →      │    │
          │  │  analyze → summarize →      │    │
          │  │  report → notify            │    │
          │  └────────────────────────────┘    │
          └──────────────────┬──────────────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │         Agent Layer                  │
          │                                     │
          │  ┌─────────────┐  ┌─────────────┐  │
          │  │news_trend   │  │viral_video  │  │
          │  │   agent     │  │   agent     │  │
          │  └─────────────┘  └─────────────┘  │
          └──────────────────┬──────────────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │      Shared Utilities Layer         │
          │                                     │
          │  ┌──────────┐  ┌──────────┐        │
          │  │  retry   │  │  cache   │        │
          │  │ (재시도)  │  │ (캐싱)   │        │
          │  └──────────┘  └──────────┘        │
          │                                     │
          │  ┌──────────┐  ┌──────────┐        │
          │  │ logging  │  │  error   │        │
          │  │(구조로깅) │  │ handling │        │
          │  └──────────┘  └──────────┘        │
          └──────────────────┬──────────────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │     External Services Layer         │
          │                                     │
          │  News APIs:                         │
          │  - NewsAPI (Global)                 │
          │  - Naver News (Korean)              │
          │                                     │
          │  Video Platforms:                   │
          │  - YouTube Data API                 │
          │  - TikTok (Official Connector)      │
          │                                     │
          │  LLM Services:                      │
          │  - Azure OpenAI (기본)              │
          │  - OpenAI / Anthropic / Google      │
          │                                     │
          │  Automation & Notification:         │
          │  - n8n Webhooks                     │
          │  - Slack Webhooks                   │
          └─────────────────────────────────────┘
```

### 기술 스택 (Tech Stack)

#### 핵심 프레임워크
- **LangGraph**: 에이전트 워크플로우 오케스트레이션
- **LangChain**: LLM 통합 및 체인 구성
- **Pydantic**: 데이터 검증 및 상태 관리
- **FastAPI**: REST API 서버 (Open WebUI 통합)

#### LLM 프로바이더 (클라우드 중립)
- Azure OpenAI (기본값)
- OpenAI API
- Anthropic Claude
- Google Gemini
- Ollama (로컬)

#### 데이터 소스
- **뉴스**: NewsAPI, Naver News, Tavily (선택)
- **영상**: YouTube Data API, TikTok (공식 커넥터)
- **자동화**: n8n, Slack

#### 인프라
- **런타임**: Python 3.11+
- **컨테이너**: Docker, Docker Compose
- **자동화**: Makefile, n8n
- **저장소**: 로컬 디스크, Redis (선택), SQLite (선택)

### 데이터 플로우 (Data Flow)

```
[User Input]
    │
    ├─ query: "전기차 트렌드"
    ├─ time_window: "7d"
    └─ language: "ko"
    │
    ▼
[collect_node] ──────────────────────────────────┐
    │                                            │
    ├─ search_news(query, time_window)          │
    │   ├─ NewsAPI → raw_items[]                │
    │   ├─ Naver API → raw_items[]              │
    │   └─ Fallback: sample_data                │
    │                                            │
    ▼ state.raw_items                            │
    │                                            │
[normalize_node] ─────────────────────────────┐  │
    │                                         │  │
    ├─ 데이터 정규화                          │  │
    ├─ 필드 표준화                            │  │
    └─ HTML 태그 제거                         │  │
    │                                         │  │
    ▼ state.normalized                        │  │
    │                                         │  │
[analyze_node] ────────────────────────────┐  │  │
    │                                      │  │  │
    ├─ analyze_sentiment(normalized)      │  │  │
    │   └─ {positive, neutral, negative}  │  │  │
    │                                      │  │  │
    ├─ extract_keywords(normalized)       │  │  │
    │   └─ {top_keywords[]}               │  │  │
    │                                      │  │  │
    ▼ state.analysis                       │  │  │
    │                                      │  │  │
[summarize_node] ───────────────────────┐  │  │  │
    │                                   │  │  │  │
    ├─ summarize_trend(LLM)             │  │  │  │
    │   └─ 트렌드 요약 + 실행 권고안     │  │  │  │
    │                                   │  │  │  │
    ▼ state.analysis.summary             │  │  │  │
    │                                   │  │  │  │
[report_node] ──────────────────────┐  │  │  │  │
    │                                │  │  │  │  │
    ├─ 마크다운 리포트 생성            │  │  │  │  │
    ├─ 메트릭 계산                    │  │  │  │  │
    │   ├─ coverage                   │  │  │  │  │
    │   ├─ factuality                 │  │  │  │  │
    │   └─ actionability              │  │  │  │  │
    │                                │  │  │  │  │
    ▼ state.report_md, metrics        │  │  │  │  │
    │                                │  │  │  │  │
[notify_node] ───────────────────┐  │  │  │  │  │
    │                            │  │  │  │  │  │
    ├─ n8n Webhook (선택)        │  │  │  │  │  │
    ├─ Slack Webhook (선택)      │  │  │  │  │  │
    │                            │  │  │  │  │  │
    ▼                            │  │  │  │  │  │
[Output] ─────────────────────┐  │  │  │  │  │  │
    │                         │  │  │  │  │  │  │
    ├─ artifacts/{agent}/{run_id}.md              │
    ├─ artifacts/{agent}/{run_id}_metrics.json    │
    └─ Notifications sent                         │
                                                  │
    공유 유틸리티 적용:                             │
    ┌─────────────────────────────────────────────┤
    │ @backoff_retry: API 호출 자동 재시도 ◄───────┤
    │ @cached: 결과 캐싱 (메모리/디스크) ◄──────────┤
    │ AgentLogger: 구조화된 JSON 로깅 ◄────────────┤
    │ PartialResult: 부분 완료 처리 ◄──────────────┘
    └─────────────────────────────────────────────┘
```

### 에이전트 상태 스키마

#### NewsAgentState
```python
{
    # Input
    "query": str,                    # 검색어
    "time_window": str,              # 기간 (예: "7d", "24h")
    "language": str,                 # 언어 (ko, en)
    "max_results": int,              # 최대 결과 수
    
    # Pipeline Data
    "raw_items": List[Dict],         # 원본 뉴스 데이터
    "normalized": List[Dict],        # 정규화된 데이터
    
    # Analysis
    "analysis": {
        "sentiment": {               # 감성 분석
            "positive": int,
            "neutral": int,
            "negative": int,
            "positive_pct": float,
            "neutral_pct": float,
            "negative_pct": float
        },
        "keywords": {                # 키워드 추출
            "top_keywords": List[Dict],
            "total_unique_keywords": int
        },
        "summary": str               # LLM 요약
    },
    
    # Output
    "report_md": str,                # 마크다운 리포트
    "metrics": {                     # 품질 메트릭
        "coverage": float,           # 커버리지 (0-1)
        "factuality": float,         # 사실성 (0-1)
        "actionability": float       # 실행 가능성 (0-1)
    },
    
    # Metadata
    "run_id": str,                   # 실행 ID (UUID)
    "error": str | None              # 에러 메시지
}
```

#### ViralAgentState
```python
{
    # Input
    "query": str,                    # 검색어
    "time_window": str,              # 기간
    "market": str,                   # 시장 (KR, US, JP)
    "platforms": List[str],          # 플랫폼 ([youtube, tiktok])
    "spike_threshold": float,        # Z-score 임계값 (기본: 2.0)
    
    # Pipeline Data
    "raw_items": List[Dict],         # 원본 영상 데이터
    "normalized": List[Dict],        # 정규화된 데이터
    
    # Analysis
    "analysis": {
        "spikes": {                  # 급상승 탐지
            "spike_videos": List[Dict],
            "mean_views": float,
            "std_views": float,
            "total_spikes": int
        },
        "clusters": {                # 토픽 클러스터링
            "top_clusters": List[Dict],
            "total_clusters": int
        },
        "success_factors": str       # 성공 요인 분석
    },
    
    # Output
    "report_md": str,                # 마크다운 리포트
    "metrics": Dict[str, float],     # 품질 메트릭
    
    # Metadata
    "run_id": str,
    "error": str | None
}
```

### 레포 구조

```
.
├─ agents/
│  ├─ news_trend_agent/
│  │  ├─ __main__.py           # CLI/HTTP 진입점
│  │  ├─ graph.py              # LangGraph 정의
│  │  ├─ prompts/              # 시스템/툴 프롬프트
│  │  ├─ tools.py              # search_news, analyze_sentiment...
│  │  ├─ POW.md                # 5~10분 검증 가이드
│  │  └─ README.md
│  ├─ viral_video_agent/
│  │  ├─ __main__.py
│  │  ├─ graph.py
│  │  ├─ prompts/
│  │  ├─ tools.py              # fetch_video_stats, detect_spike...
│  │  ├─ POW.md
│  │  └─ README.md
│  └─ shared/                  # 공통(캐싱/로깅/가드레일/HTTP 클라이언트)
├─ automation/
│  ├─ n8n/                     # 워크플로우 export JSON
│  └─ mcp/                     # MCP 설정/README
├─ playbooks/                  # QUICK_START, USAGE, EVALS
├─ scripts/
│  └─ run_agent.py             # --agent 분기, POW 실행 유틸
├─ artifacts/                  # 에이전트별 산출물(MD/PNG/CSV)
├─ docs/                       # 아키텍처/운영/데모 GIF
├─ docker-compose.yml
├─ Makefile
├─ .env.example
└─ README.md
```

---

## ⚙️ 설치 및 실행

### 요구사항
- **Docker & Docker Compose** (권장)
- **Python 3.11+**
- **Node.js 22.x** (Frontend 개발 시)

### 1) 환경 변수

```bash
cp .env.example .env
```

필수/선택 항목은 [환경 변수](#-환경-변수env) 섹션 참조.

### 2) 실행

**옵션 A: Docker (권장)**

```bash
docker compose up -d --build
```

**옵션 B: Makefile**

```bash
make install && make build && make up
make logs
```

**옵션 C: 로컬 (개발)**

```bash
# backend
cd backend && pip install -r requirements.txt
uvicorn open_webui.main:app --host 0.0.0.0 --port 8080 --reload

# frontend (Open WebUI or Dev UI)
npm ci --legacy-peer-deps
npm run dev
```

**접속:**
- WebUI: http://localhost:3000 (또는 5173)
- API: http://localhost:8080

---

## 🔬 빠른 검증(POW)

### POW-1: 뉴스 트렌드 리포트

```bash
python scripts/run_agent.py --agent news_trend_agent \
  --query "foldable phone reactions in Korea" \
  --window last_24h --emit md --notify n8n,slack
```

### POW-2: 바이럴 급상승 탐지

```bash
python scripts/run_agent.py --agent viral_video_agent \
  --market KR --platform youtube,tiktok \
  --emit md --notify n8n
```

### 성공 기준
- ✅ 감성/키워드/핵심인사이트 + 출처 Top-N 포함된 MD 생성
- ✅ 알림 전송 성공(n8n/Slack)
- ✅ `/artifacts/<agent>/` 경로에 산출물/로그 저장

---

## 🔑 환경 변수(.env)

```bash
# LLM Configuration (Cloud-Neutral)
LLM_PROVIDER=azure_openai  # azure_openai, openai, anthropic, google, ollama

# Azure OpenAI (기본값)
OPENAI_API_TYPE=azure
OPENAI_API_BASE=https://your-resource.openai.azure.com/
OPENAI_API_KEY=your-api-key
OPENAI_API_VERSION=2024-02-15-preview
OPENAI_DEPLOYMENT_NAME=gpt-4
OPENAI_MODEL_NAME=gpt-4

# OpenAI (LLM_PROVIDER=openai 시)
# OPENAI_API_KEY=sk-your-openai-api-key
# OPENAI_MODEL_NAME=gpt-4-turbo-preview

# Anthropic (LLM_PROVIDER=anthropic 시)
# ANTHROPIC_API_KEY=sk-ant-your-key
# ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022

# Google (LLM_PROVIDER=google 시)
# GOOGLE_API_KEY=your-google-api-key
# GOOGLE_MODEL_NAME=gemini-1.5-pro

# Ollama (LLM_PROVIDER=ollama 시)
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL_NAME=llama3.1

# 데이터 소스(선택)
NEWS_API_KEY=...
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...

# SNS/동영상 커넥터(선택)
YOUTUBE_API_KEY=...
TIKTOK_CONNECTOR_TOKEN=...
INSTAGRAM_CONNECTOR_TOKEN=...

# 알림/자동화(선택)
SLACK_WEBHOOK_URL=...
N8N_WEBHOOK_URL=https://your-n8n/webhook/trend
```

**키가 없으면 샘플 데이터로 자동 전환됩니다.**

---

## 🧪 사용 예시

### CLI

```bash
python scripts/run_agent.py --agent news_trend_agent \
  --query "vegan snacks" --window 7d --emit md
```

### WebUI
1. 에이전트 선택
2. 질의 입력
3. 스트리밍 응답 확인

### n8n 연동
- `/automation/n8n/*.json` 가져오기
- 크론/웹훅/Slack 연결
- 자동 실행 설정

---

## 🔧 커스터마이징

### 시스템 프롬프트
- `agents/*/prompts/system.md` 수정
- 증거 우선/수치 우선/안전 규칙 유지 권장

### 도구 추가
- `agents/*/tools.py`에 새 도구 추가
- `fetch_*`, `analyze_*`, `summarize_*`, `report_*` 패턴 권장

### n8n 연동
- `/automation/n8n/*.json` 워크플로우 커스터마이징
- 재시도/백오프: 2^k, 최대 5회 권장

### MCP 연동
- `/automation/mcp/README.md` 가이드 참조
- 모델이 파일/검색/브라우저 도구 사용 가능

---

## 🛡 운영·보안

- **레이트리밋/타임아웃/캐싱**: TTL 적용
- **PII 마스킹**: 옵션 제공
- **저작권/허위정보**: 경고 문구 자동 포함
- **로깅**: JSON 라인 로깅 + run_id로 트레이싱
- **실패 처리**: 부분 완료 표기 및 근거/한계 명시

---

## 📝 라이선스

MIT License
기반: [Open WebUI](https://github.com/open-webui/open-webui)

---

## 📚 추가 문서

- [QUICK_START.md](playbooks/QUICK_START.md) - 5분 안에 시작하기
- [DESIGN_DOC.md](docs/DESIGN_DOC.md) - 개발 설계서
- [CLAUDE_CODE_RULES.md](CLAUDE_CODE_RULES.md) - Claude Code 작업 규칙
- [각 에이전트 POW.md](agents/) - 에이전트별 검증 가이드