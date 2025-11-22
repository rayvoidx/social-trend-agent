# AI 트렌드 분석 에이전트 시스템 v0.1

> **릴리즈 노트** - 2025-11-20

---

## 📦 릴리즈 요약

LangGraph 기반 멀티 에이전트 시스템의 첫 번째 공식 릴리즈입니다. 3개의 특화된 에이전트를 통해 뉴스, 바이럴 비디오, 소셜 미디어 트렌드를 자동으로 수집·분석·요약합니다.

---

## ✅ 구현 완료 기능

### 🤖 에이전트 시스템

#### News Trend Agent
- 뉴스 데이터 수집 (NewsAPI, Naver News API)
- 감성 분석 (긍정/중립/부정 분류)
- 키워드 추출 (빈도 기반)
- LLM 기반 인사이트 생성
- 마크다운 리포트 자동 생성

#### Viral Video Agent
- YouTube Data API v3 연동
- 급상승 감지 (Z-Score 기반)
- 성공 요인 분석 (5가지 핵심 요소)
- 플랫폼별 최적화 전략 제안
- Webhook 알림 연동

#### Social Trend Agent
- 멀티 플랫폼 데이터 수집 (X, Instagram, Naver Blog, RSS)
- 바이럴 요소 분석
- 소비자 목소리 추출
- 실행 가능한 마케팅 인사이트 생성

### 🔧 핵심 인프라

#### LLM 지원
- OpenAI GPT-4o (기본 권장)
- Azure OpenAI (엔터프라이즈)
- Anthropic Claude 3.5 Sonnet
- Google Gemini 1.5 Pro
- Ollama (로컬 LLM)

#### 프로덕션 기능
- 재시도 로직 (지수 백오프)
- 구조화된 로깅 (JSON, run_id 추적)
- TTL 기반 캐싱
- PII 마스킹 가드레일
- 부분 결과 처리

#### API 서버
- FastAPI 기반 REST API
- WebSocket 실시간 메트릭 스트림
- 분산 작업 실행기 (4 워커)
- n8n 웹훅 라우트

#### 자동화
- n8n 워크플로우 (일일 브리핑, 바이럴 알림)
- Slack 웹훅 알림
- MCP 서버 (Claude Desktop 연동)

---

## ⚠️ 현재 제한사항

### 데이터 소스
- **X(Twitter)**: Bearer Token 필요, Rate Limit 존재
- **Instagram**: Business API 연동 필요 (현재 샘플 데이터)
- **TikTok**: 서드파티 API 사용 (공식 API 제한적)
- **API 키 미설정 시**: 샘플 데이터로 폴백

### 시스템
- **작업 저장소**: 메모리 기반 (서버 재시작 시 손실)
- **동시성**: 단일 프로세스 내 비동기 처리
- **인증**: API 키 기반만 지원 (JWT 미구현)

### 분석 품질
- **감성 분석**: 키워드 기반 (ML 모델 미적용)
- **다국어**: 한국어/영어만 최적화
- **실시간성**: 배치 처리 방식 (스트리밍 미지원)

---

## 🚀 다음 단계 (v0.2 계획)

### Phase 1: 프롬프트 고도화
- [ ] 마케터 관점 톤 최적화
- [ ] "바로 실행 가능한 액션 3~5개" 섹션 강화
- [ ] 도메인별 Few-Shot 예시 보강

### Phase 2: 도메인 모델 연동
- [ ] Mission/Creator/Reward/Insight 개념 문서화
- [ ] 인사이트 → 미션 생성 프롬프트
- [ ] 미션 → 크리에이터 매칭 프롬프트

### Phase 3: 인프라 개선
- [ ] Redis 기반 작업 저장소
- [ ] 분석 결과 DB 영구 저장
- [ ] JWT 기반 인증
- [ ] Prometheus + Grafana 모니터링

### Phase 4: 분석 품질 개선
- [ ] ML 기반 감성 분석
- [ ] 실시간 WebSocket 스트리밍
- [ ] Celery 기반 대량 배치 처리

---

## 📊 프로젝트 구조

```
social-trend-agent/
├── agents/
│   ├── news_trend_agent/        # 뉴스 트렌드 분석
│   │   ├── graph.py              # LangGraph 워크플로우
│   │   ├── tools.py              # 데이터 수집/분석 도구
│   │   ├── prompts.py            # 시스템 프롬프트
│   │   └── prompts/              # 마크다운 프롬프트 템플릿
│   │
│   ├── viral_video_agent/       # 바이럴 비디오 분석
│   │   ├── graph.py              # YouTube API + Webhook
│   │   ├── tools.py              # 바이럴 감지 도구
│   │   └── prompts.py            # 프롬프트
│   │
│   ├── social_trend_agent/      # 소셜 미디어 분석
│   │   ├── graph.py              # LLM 인사이트 생성
│   │   ├── tools.py              # 멀티 플랫폼 수집
│   │   └── prompts.py            # 소셜 미디어 프롬프트
│   │
│   ├── api/                     # FastAPI 서버
│   │   ├── dashboard.py          # 메인 API
│   │   ├── n8n_routes.py         # n8n 웹훅
│   │   └── analysis_service.py   # 분석 서비스
│   │
│   └── shared/                  # 공유 유틸리티
│       ├── state.py              # Pydantic 상태 모델
│       ├── distributed.py        # 분산 실행기
│       ├── monitoring.py         # 메트릭 수집
│       └── retrieval/            # RAG 컴포넌트
│
├── automation/                  # 자동화
│   ├── mcp/                      # MCP 서버
│   └── n8n/                      # n8n 워크플로우
│
├── main.py                      # CLI 진입점
├── requirements.txt
└── docker-compose.yaml
```

---

## 🔧 빠른 시작

### 설치
```bash
git clone https://github.com/rayvoidx/social-trend-agent.git
cd social-trend-agent
pip install -r requirements.txt
```

### 환경 설정
```bash
cp .env.example .env
# .env 파일에 OPENAI_API_KEY 추가
```

### 실행
```bash
# 뉴스 트렌드 분석
python main.py --agent news_trend_agent --query "AI" --window 7d

# 바이럴 비디오 분석
python main.py --agent viral_video_agent --query "K-pop" --market KR

# 소셜 트렌드 분석
python main.py --agent social_trend_agent --query "ChatGPT" --sources x naver_blog
```

---

## 📝 API 사용

### 에이전트 실행
```http
POST /n8n/agent/execute
Content-Type: application/json

{
  "agent": "social_trend_agent",
  "query": "AI trends",
  "time_window": "7d",
  "notify_slack": true
}
```

### 작업 상태 조회
```http
GET /n8n/agent/status/{task_id}
```

### 대시보드 요약
```http
GET /api/dashboard/summary
```

---

## 🔑 환경 변수

### 필수
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL_NAME=gpt-4o
```

### 선택 (데이터 소스)
```bash
NEWS_API_KEY=              # 영문 뉴스
NAVER_CLIENT_ID=           # 한글 뉴스
NAVER_CLIENT_SECRET=
YOUTUBE_API_KEY=           # 바이럴 비디오
X_BEARER_TOKEN=            # Twitter/X
```

### 선택 (알림)
```bash
SLACK_WEBHOOK_URL=
N8N_WEBHOOK_URL=
```

---

## 📚 관련 문서

- [README.md](README.md) - 전체 프로젝트 개요 및 유즈케이스
- [automation/n8n/README.md](automation/n8n/README.md) - n8n 워크플로우 가이드
- [automation/mcp/README.md](automation/mcp/README.md) - MCP 서버 설정
- [.env.example](.env.example) - 환경 변수 전체 목록

---

## 🏷️ 버전 정보

- **버전**: v0.1.0
- **릴리즈 날짜**: 2025-11-20
- **Python**: 3.11+
- **LangGraph**: 0.2+
- **FastAPI**: 0.115+

---

## 📧 문의

**GitHub**: [@rayvoidx](https://github.com/rayvoidx)

---

*이 문서는 AI 트렌드 분석 에이전트 시스템의 현재 상태와 향후 계획을 정리한 릴리즈 노트입니다.*
