# 개발 설계서 (Design Document)

> **소비자 트렌드 자동 분석 에이전트 - 토탈 시스템 아키텍처**

**버전**: 1.0.0
**최종 업데이트**: 2024-10-19
**작성자**: Trend Analysis Team

---

## 📋 목차

1. [배경과 목표](#1-배경과-목표)
2. [범위 / 비범위](#2-범위--비범위)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [레포 구조](#4-레포-구조)
5. [주요 컴포넌트 설계](#5-주요-컴포넌트-설계)
6. [데이터 모델](#6-데이터-모델)
7. [환경 변수 스키마](#7-환경-변수-스키마)
8. [실행 및 검증(POW)](#8-실행-및-검증pow)
9. [평가(Evals)](#9-평가evals)
10. [관측/로깅/장애대응](#10-관측로깅장애대응)
11. [보안/정책](#11-보안정책)
12. [로드맵](#12-로드맵)
13. [Claude Code 작업 규칙](#13-claude-code-작업-규칙)
14. [참고 자료](#14-참고-자료)

---

## 1. 배경과 목표

### 1.1 배경

기업의 마케팅·상품기획 부서는 빠르게 변화하는 소비자 트렌드를 파악하기 위해 수동으로 뉴스, SNS, 동영상 플랫폼을 모니터링해야 하는 부담이 있습니다. 이는 시간 소모적이며, 중요한 신호를 놓칠 위험이 있습니다.

### 1.2 목표

**"뉴스·SNS·동영상 전 채널의 트렌드/반응을 자동 수집·분석·요약해, 하루 단위가 아닌 '분 단위'로 전략을 검증·실행하도록 돕는 토탈 에이전트 시스템 구축"**

### 1.3 채용요건 정렬 (삼양 AI Agent Builder)

| 요구사항 | 레포 근거 |
|---------|----------|
| **최근 1개월 내 2개+ 실전 에이전트** | `agents/news_trend_agent`, `agents/viral_video_agent` (각각 POW, 산출물) |
| **n8n·LLM API·MCP 실전** | `/automation/n8n/*.json`, `.env.example`(Azure OpenAI), `/automation/mcp/` |
| **프롬프트 엔지니어링 + 시스템 설계** | 각 에이전트 `prompts/`, `graph.py`(ReAct/툴 라우팅/가드레일), 본 문서 |
| **실험·실행 우선(작동물)** | `playbooks/QUICK_START.md`, 각 `POW.md`, `/artifacts/` 데모 산출물 |

---

## 1. 범위 / 비범위

### 범위
- 데이터 수집(뉴스/동영상)
- 정규화
- 감성/키워드/바이럴 신호 분석
- 리포트 생성
- Slack/n8n 알림
- 샘플 데이터로 키 없이 로컬 검증
- LangGraph 기반 오케스트레이션

### 비범위
- 크롤링으로 정책 위반이 되는 행위
- 비공식/불법 API 사용 강제 (공식 API/합법적 커넥터만 명시)

---

## 2. 아키텍처 (개요)

\`\`\`
┌──────── Open WebUI ────────┐   Chat/Prompt
│  Agent Selector            │ ───────────────▶ CLI/HTTP Entrypoints
└───────────┬────────────────┘
            │
      ┌─────▼───── LangGraph Orchestrator ─────┐
      │  ReAct + Tools + StateGraph            │
      └─────┬──────────────────────────────────┘
            │
   ┌────────▼──────── Tool Layer ──────────────────────────┐
   │ search_news / analyze_sentiment / extract_keywords     │
   │ fetch_video_stats / detect_spike / topic_cluster       │
   │ summarize_trend / report_markdown / webhooks           │
   └────────┬───────────────────────────────────────────────┘
            │
   ┌────────▼──────── Data/Automation ──────────────────────┐
   │ News API / Naver / (opt) Tavily                        │
   │ YouTube / TikTok / Instagram(공식/서드파티 커넥터)     │
   │ n8n (cron/webhook/Slack/Sheets)                        │
   │ Disk/Blob/DB (Redis/SQLite/Vector)                     │
   └────────────────────────────────────────────────────────┘
\`\`\`

---

## 3. 레포 구조(권장, Monorepo)

\`\`\`
.
├─ agents/
│  ├─ news_trend_agent/
│  │  ├─ __main__.py
│  │  ├─ graph.py
│  │  ├─ prompts/
│  │  ├─ tools.py
│  │  ├─ POW.md
│  │  └─ README.md
│  ├─ viral_video_agent/
│  │  ├─ __main__.py
│  │  ├─ graph.py
│  │  ├─ prompts/
│  │  ├─ tools.py
│  │  ├─ POW.md
│  │  └─ README.md
│  ├─ creator_onboarding_agent/ (선택)
│  └─ shared/
├─ automation/
│  ├─ n8n/
│  └─ mcp/
├─ playbooks/
├─ scripts/
├─ artifacts/
├─ docs/
└─ README.md
\`\`\`

---

## 4. 주요 컴포넌트 설계

### 4.1 에이전트 상태 & 그래프(LangGraph)

**State 스키마(공통)**

\`\`\`python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class AgentState(BaseModel):
    query: str
    time_window: Optional[str] = None
    raw_items: List[Dict[str, Any]] = []
    normalized: List[Dict[str, Any]] = []
    analysis: Dict[str, Any] = {}
    report_md: Optional[str] = None
    metrics: Dict[str, float] = {}  # coverage, factuality, actionability
\`\`\`

**노드 정석**
- collect → normalize → analyze → summarize → report → notify
- 실패시 backoff_retry(node) 데코레이터로 지수 백오프(2^k, max=5)

### 4.2 Tool Layer (핵심 메서드)

| Tool | 설명 |
|------|------|
| `search_news(query, window)` | News/Naver/Tavily |
| `analyze_sentiment(texts)` | LLM+통계 결합, 긍/부/중 |
| `extract_keywords(texts)` | 빈도/스코어 기반 Top-N |
| `fetch_video_stats(platform, market)` | YouTube/TikTok 지표 |
| `detect_spike(timeseries)` | z-score/단순 이동 평균 기반 스파이크 |
| `topic_cluster(texts)` | TF-IDF + KMeans or LLM 토픽 |
| `report_markdown(analysis, evidence)` | MD 리포트 템플릿 |
| `send_webhook(md)` | Slack/n8n 알림 |

### 4.3 프롬프트/가드레일

**원칙:**
1. 증거 우선(출처 Top-N 링크 강제)
2. 수치 우선(가능한 정량)
3. 정책/안전 문구(저작권/허위정보 경고)

**시스템 프롬프트 핵심 규칙:**
- "요약은 출처 ID와 함께"
- "추정은 추정으로 명시"
- "PII·정책 위반 회피"

### 4.4 데이터 모델 (요약)

- **raw_items**: `{source, url, title, text, ts, meta}`
- **normalized**: `{id, lang, cleaned_text, channel, tags}`
- **analysis**: `{sentiment: {pos, neg, neu}, keywords: [...], topics: [...], viral: {...}}`
- **metrics**: `{coverage, factuality, actionability}`

---

## 5. 환경변수 스키마 (.env.example)

### LLM Configuration (Cloud-Neutral)

| KEY | 설명 | 필수 | 기본값 |
|-----|------|------|--------|
| LLM_PROVIDER | LLM 제공자 선택 | Y | azure_openai |
| OPENAI_API_TYPE | OpenAI API 타입 | Y (Azure) | azure |
| OPENAI_API_BASE | OpenAI/Azure Endpoint | Y | - |
| OPENAI_API_KEY | API Key | Y | - |
| OPENAI_API_VERSION | API Version | Y (Azure) | 2024-02-15-preview |
| OPENAI_DEPLOYMENT_NAME | Deployment/Model Name | Y | gpt-4 |
| OPENAI_MODEL_NAME | Model Name | Y | gpt-4 |

**지원 LLM 제공자:**
- `azure_openai` - Azure OpenAI Service (기본값)
- `openai` - OpenAI API
- `anthropic` - Anthropic Claude
- `google` - Google Gemini
- `ollama` - Ollama (로컬)

### 데이터 소스 & 알림

| KEY | 설명 | 필수 |
|-----|------|------|
| NEWS_API_KEY | NewsAPI (선택) | N |
| NAVER_CLIENT_ID / SECRET | Naver Open API (선택) | N |
| YOUTUBE_API_KEY | YouTube Data API (선택) | N |
| TIKTOK_CONNECTOR_TOKEN | 합법적 커넥터 토큰 | N |
| SLACK_WEBHOOK_URL | Slack 알림 | N |
| N8N_WEBHOOK_URL | n8n Webhook | N |

**키가 없으면 샘플 데이터로 graceful fallback.**

---

## 6. 실행/검증(POW)

### POW-1 뉴스 트렌드

\`\`\`bash
python scripts/run_agent.py --agent news_trend_agent \\
  --query "foldable phone reactions in Korea" --window last_24h \\
  --emit md --notify n8n,slack
\`\`\`

### POW-2 바이럴 급상승

\`\`\`bash
python scripts/run_agent.py --agent viral_video_agent \\
  --market KR --platform youtube,tiktok --emit md --notify n8n
\`\`\`

---

## 7. 평가(Evals)

- **Coverage**: 사용한 근거 링크/전체 후보 링크 비율
- **Factuality**: 요약 문장 ↔ 근거 문장 정합 스코어
- **Actionability**: 리포트가 '실행 가능한' 제안 포함 여부

---

## 8. 관측/로깅/장애대응

- JSON 구조 로그 + run_id 발급 → 재실행 트래킹
- 리트라이/백오프(2^k) + 캐싱 TTL
- 실패 시 산출물에 "부분 완료" 표시, 근거/한계 명시

---

## 9. 보안/정책

- 외부 API 레이트리밋 준수
- PII 마스킹 옵션
- 저작권·브랜드 세이프티 체크
- 플랫폼 정책 범위 내 API/커넥터만 사용

---

## 10. 로드맵(요약)

- **v0.1**: news/viral 2개 에이전트 + n8n + POW + 샘플 데이터
- **v0.2**: creator_onboarding_agent + MCP 연계 강화
- **v0.3**: Vector DB/검색(선택) + 자동 벤치/리그레션 Evals 파이프

---

## 11. 참고 문서

- [README.md](../README.md) - 프로젝트 개요
- [CLAUDE_CODE_RULES.md](../CLAUDE_CODE_RULES.md) - 작업 규칙
- [각 에이전트 POW.md](../agents/) - 검증 가이드
