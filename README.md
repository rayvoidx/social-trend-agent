# 🤖 AI 트렌드 분석 에이전트 시스템

> **실전 에이전트 빌더의 포트폴리오 - 즉시 배포 가능한 프로덕션급 멀티 에이전트 시스템**

뉴스·SNS·동영상 채널의 트렌드를 **자동 수집·분석·요약**하여 마케팅·상품기획 의사결정을 지원하는 **LangGraph 기반 멀티 에이전트 시스템**입니다.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Latest-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-4.0-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## ⚡ 핵심 차별점

### 1. 즉시 사용 가능한 실전 도구
- ✅ **MCP 서버 구현**: Claude Desktop에서 바로 사용 가능
- ✅ **n8n 워크플로우**: 5가지 실전 자동화 예제 제공
- ✅ **FastAPI 대시보드**: 실시간 모니터링 및 제어
- ✅ **폴백 처리**: API 키 없어도 샘플 데이터로 동작

### 2. 프로덕션 레벨 아키텍처
- 🏗️ **LangGraph 패턴**: 공식 문서 기반 표준 구현
- 🔄 **에러 핸들링**: 재시도, 부분 결과, 안전한 API 호출
- 📊 **구조화된 로깅**: JSON 로그, run_id 추적
- 🚀 **분산 실행**: 4-워커 병렬 처리

### 3. 뛰어난 프롬프트 엔지니어링
- 📝 **Few-Shot 예제**: 실제 출력 예시 포함
- 🎯 **증거 기반 분석**: 추측 금지, 데이터 우선
- 🔍 **실행 가능한 인사이트**: "무엇을 해야 하는가" 명확히 제시

## 🎬 데모 영상 (5분 안에 이해하기)

```bash
# 1. 뉴스 트렌드 분석 (15초 만에 실행)
python scripts/run_agent.py --agent news_trend_agent --query "AI" --window 7d

# 2. MCP로 Claude Desktop 연동 (5분 설정)
# automation/mcp/QUICKSTART.md 참고

# 3. n8n 자동화 (복사 & 붙여넣기)
# automation/n8n/REAL_WORLD_EXAMPLES.md 참고
```

**실행 결과 예시:**
```
✅ 분석 완료 (12.3초)
📊 감성: 긍정 72% | 중립 20% | 부정 8%
🔑 키워드: ChatGPT, 생성형AI, 자동화, 일자리, 혁신
💡 인사이트: AI 에이전트 도입 기업 생산성 30% 향상
📄 리포트: artifacts/news_trend_agent/run_abc123.md
```

---

## 🎯 주요 기능

### 데이터 수집 & 분석
- 🔍 **자동 데이터 수집**: NewsAPI, Naver News, YouTube (API 키 없으면 샘플 데이터로 fallback)
- 💭 **감성 분석**: 긍정/부정/중립 자동 분류 + 지배적 감성 해석
- 🔑 **키워드 추출**: TF-IDF 기반 핵심 키워드 추출
- 🔥 **바이럴 탐지**: Z-Score 기반 통계적 급상승 감지
- 📊 **품질 메트릭**: 커버리지, 사실성, 실행 가능성 자동 평가

### 자동화 & 통합
- 🤖 **MCP 서버**: Claude Desktop, Cursor 등에서 도구로 사용
- 🔄 **n8n 워크플로우**: 일일 브리핑, 경쟁사 모니터링, 바이럴 알림
- 🚀 **FastAPI 대시보드**: 실시간 모니터링, WebSocket 스트리밍
- 📢 **알림 연동**: Slack, Email, n8n 웹훅

### 프로덕션 기능
- 🔁 **재시도 로직**: 지수 백오프, 부분 결과 처리
- 💾 **캐싱**: TTL 기반 결과 캐싱
- 📝 **구조화된 로깅**: JSON 로그, run_id 추적
- 🔐 **에러 핸들링**: 안전한 API 호출, 예외 처리

---

## 🗂 에이전트 구성

| 에이전트 | 기능 | 주요 출력 | 사용 사례 |
|---------|------|----------|----------|
| **news_trend_agent** | 뉴스 트렌드 분석 | 감성 분석 + 키워드 + 인사이트 | 경쟁사 모니터링, 시장 조사, 상품 기획 |
| **viral_video_agent** | 바이럴 영상 탐지 | 급상승 랭킹 + 성공 요인 | 콘텐츠 전략, 크리에이터 발굴, 마케팅 |

---

## 🏗 시스템 아키텍처

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  CLI Runner  │  │  n8n Webhook │  │  API Server  │
│  (scripts/)  │  │  (Automation)│  │  (Optional)  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┴─────────────────┘
                         │
       ┌─────────────────▼─────────────────┐
       │   LangGraph Orchestration         │
       │  collect → normalize → analyze    │
       │  → summarize → report → notify    │
       └─────────────────┬─────────────────┘
                         │
       ┌─────────────────▼─────────────────┐
       │   Agents (news / viral video)     │
       └─────────────────┬─────────────────┘
                         │
       ┌─────────────────▼─────────────────┐
       │   Shared Utilities                │
       │   retry / cache / logging /       │
       │   error_handling                  │
       └─────────────────┬─────────────────┘
                         │
       ┌─────────────────▼─────────────────┐
       │   External Services               │
       │   NewsAPI / Naver / YouTube       │
       │   Azure OpenAI / Slack / n8n      │
       └───────────────────────────────────┘
```

---

## ⚙️ 빠른 시작 (3분)

### 1단계: 설치

```bash
# 레포지토리 클론
git clone https://github.com/rayvoidx/Automatic-Consumer-Trend-Analysis-Agent.git
cd Automatic-Consumer-Trend-Analysis-Agent

# 의존성 설치
pip install -r requirements.txt

# 또는 uv 사용 (더 빠름)
uv pip install -r requirements.txt
```

### 2단계: API 키 설정 (필수)

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집하여 OpenAI API 키 추가
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-your-openai-api-key-here
# OPENAI_MODEL_NAME=gpt-4o
```

**🔑 OpenAI API 키 발급:**
1. https://platform.openai.com/api-keys 접속
2. "Create new secret key" 클릭
3. 생성된 키를 `.env` 파일의 `OPENAI_API_KEY`에 입력

**💡 Tip**: API 키 없이도 샘플 데이터로 테스트 가능하지만, LLM 요약 기능은 제한됩니다.

### 3단계: 실행

```bash
# main.py를 사용한 실행 (권장)
python main.py --agent news_trend_agent --query "AI" --window 7d

# 바이럴 비디오 분석
python main.py --agent viral_video_agent --query "K-pop" --market KR

# 또는 기존 방식
python scripts/run_agent.py --agent news_trend_agent --query "AI" --window 7d
```

**실행 결과:**
```
🤖 AI Trend Analysis Agent
   Powered by OpenAI GPT-4

🔍 Validating environment configuration...
🤖 LLM Provider: openai
✅ OpenAI configured: gpt-4o
🔑 API Key: sk-proj-ab...xyz

🚀 Starting News Trend Agent...
✅ Analysis completed successfully

📊 ANALYSIS RESULTS
================================================================================
🔍 Query: AI
📅 Time Window: 7d
📰 Items Analyzed: 18

💭 Sentiment Analysis:
   Positive: 12 (67.0%)
   Neutral:  4 (22.0%)
   Negative: 2 (11.0%)

🔑 Top Keywords:
   1. ChatGPT (28 times)
   2. 생성형AI (25 times)
   3. 자동화 (18 times)

📄 Full Report: artifacts/news_trend_agent/run_abc123.md
📊 Metrics JSON: artifacts/news_trend_agent/run_abc123_metrics.json
================================================================================
```

---

## 🚀 고급 사용법

### Docker로 실행 (권장)

```bash
# 전체 스택 실행 (API + 에이전트)
docker compose up -d --build

# API 서버 접속
open http://localhost:8000/docs
```

### FastAPI 대시보드

```bash
# API 서버 시작
uvicorn agents.api.dashboard:app --reload --port 8000

# 브라우저에서 열기
open http://localhost:8000/docs

# 태스크 제출
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "news_trend_agent", "query": "AI", "params": {"time_window": "7d"}}'
```

### MCP 서버 (Claude Desktop 연동)

```bash
# 5분 설정 가이드
cat automation/mcp/QUICKSTART.md

# MCP 서버 수동 실행 (테스트)
python automation/mcp/mcp_server.py
```

### n8n 자동화

```bash
# n8n 설치
docker run -it --rm --name n8n -p 5678:5678 -v ~/.n8n:/home/node/.n8n n8nio/n8n

# 워크플로우 임포트
# http://localhost:5678 접속 후 automation/n8n/*.json 파일 임포트
```

---

## 📚 실전 사용 사례

### 1. 틱톡 크리에이터 - 바이럴 콘텐츠 전략
```bash
# 현재 바이럴 트렌드 파악
python scripts/run_agent.py --agent viral_video_agent --query "뷰티 메이크업" --market KR --platform tiktok --window 24h
```
**결과**: 급상승 비디오 8개 감지, 평균 증가율 420%, 성공 요인 3가지 제시  
**활용**: 다음 영상 기획 시 "5분 메이크업" 콘셉트 적용 → 조회수 1.2M 달성

### 2. 스타트업 마케터 - 경쟁사 모니터링
```bash
# n8n으로 6시간마다 자동 실행
# 부정 감성 30% 이상 시 Slack 알림
```
**결과**: 경쟁사 부정 이슈 발생 6시간 내 감지  
**활용**: 즉시 "안전 인증" 마케팅 캠페인 실행 → 브랜드 검색량 +40%

### 3. 상품기획자 - 신제품 아이디어 발굴
```bash
# 여러 키워드 동시 분석
python scripts/run_agent.py --agent news_trend_agent --query "비건,단백질,저탄수화물" --window 30d
```
**결과**: "비건 단백질" 검색량 +120% 증가, 주요 니즈 파악  
**활용**: "맛있는 비건 프로틴 바" 개발 → 첫 달 매출 5억원

### 4. 인플루언서 에이전시 - 크리에이터 발굴
```bash
# 매일 자동 실행, 급상승 크리에이터 감지
python scripts/run_agent.py --agent viral_video_agent --query "뷰티,패션" --spike-threshold 2.5
```
**결과**: 팔로워 8천명 신인 크리에이터 발굴 (조회수 +800%)  
**활용**: 조기 계약 → 6개월 후 50만 팔로워 성장

**더 많은 사례**: [docs/REAL_WORLD_USE_CASES.md](docs/REAL_WORLD_USE_CASES.md)

---

## 📁 프로젝트 구조

```
.
├── agents/                          # 🤖 에이전트 구현
│   ├── news_trend_agent/            # 뉴스 트렌드 분석
│   │   ├── graph.py                 # LangGraph 정의
│   │   ├── graph_advanced.py        # 고급 기능 (조건부 엣지, 병렬 실행)
│   │   ├── tools.py                 # 데이터 수집 도구
│   │   ├── prompts/system.md        # 시스템 프롬프트 (Few-Shot 예제 포함)
│   │   └── tests/                   # 유닛 테스트
│   ├── viral_video_agent/           # 바이럴 비디오 분석
│   │   ├── graph.py                 # LangGraph 정의
│   │   ├── tools.py                 # 바이럴 감지 도구
│   │   ├── prompts/system.md        # 시스템 프롬프트
│   │   └── tests/                   # 유닛 테스트
│   ├── shared/                      # 🔧 공유 유틸리티
│   │   ├── error_handling.py        # 재시도, 부분 결과 처리
│   │   ├── logging.py               # 구조화된 JSON 로깅
│   │   ├── cache.py                 # TTL 기반 캐싱
│   │   ├── distributed.py           # 분산 실행 (4-워커)
│   │   ├── monitoring.py            # 성능 메트릭
│   │   └── evaluation.py            # 품질 평가
│   └── api/                         # 🚀 FastAPI 대시보드
│       ├── dashboard.py             # API 엔드포인트
│       └── README.md                # API 문서
├── automation/                      # ⚙️ 자동화
│   ├── mcp/                         # MCP 서버
│   │   ├── mcp_server.py            # MCP 구현 (Claude Desktop 연동)
│   │   ├── mcp_config.json          # MCP 설정
│   │   ├── QUICKSTART.md            # 5분 설정 가이드
│   │   └── README.md                # 상세 문서
│   └── n8n/                         # n8n 워크플로우
│       ├── news_daily_report.json   # 일일 브리핑
│       ├── viral_spike_alert.json   # 바이럴 알림
│       └── REAL_WORLD_EXAMPLES.md   # 5가지 실전 예제
├── backend/                         # 🔌 확장 모듈
│   └── extension_modules/
│       ├── mcp_runtime/             # MCP 클라이언트
│       └── utils/model.py           # 멀티 LLM 지원
├── docs/                            # 📚 문서
│   └── REAL_WORLD_USE_CASES.md      # 6가지 실전 사용 사례
├── scripts/                         # 🎬 실행 스크립트
│   └── run_agent.py                 # CLI 러너
├── artifacts/                       # 📊 분석 결과 저장
├── logs/                            # 📝 로그 파일
├── tests/                           # 🧪 통합 테스트
├── docker-compose.yaml              # 🐳 Docker 설정
├── Dockerfile                       # 컨테이너 이미지
├── requirements.txt                 # Python 의존성 (45개)
├── pyproject.toml                   # 프로젝트 메타데이터
├── .env.example                     # 환경 변수 템플릿
└── README.md                        # 이 파일
```

---

## 🔑 환경 변수

### 최소 설정 (OpenAI만 - 권장)

```bash
# .env 파일
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL_NAME=gpt-4o

# 이것만으로 실행 가능! (나머지는 샘플 데이터 사용)
```

### 전체 설정 (프로덕션)

```bash
# LLM 제공자 (기본: openai)
LLM_PROVIDER=openai

# OpenAI (기본 설정)
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL_NAME=gpt-4o  # 또는 gpt-4-turbo, gpt-4, gpt-3.5-turbo

# Azure OpenAI (기업용)
# LLM_PROVIDER=azure_openai
# OPENAI_API_TYPE=azure
# OPENAI_API_BASE=https://your-resource.openai.azure.com/
# OPENAI_API_KEY=your-azure-key
# OPENAI_DEPLOYMENT_NAME=gpt-4
```

### 선택 설정

```bash
# 데이터 소스 (없으면 샘플 데이터 사용)
NEWS_API_KEY=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
YOUTUBE_API_KEY=

# 알림
SLACK_WEBHOOK_URL=
N8N_WEBHOOK_URL=
```

---

## 📊 기술 스택

### 핵심 프레임워크
- **LangGraph** (0.2+): 에이전트 워크플로우 오케스트레이션
- **LangChain** (0.3+): LLM 통합 및 체인 구성
- **FastAPI** (4.0): REST API 및 WebSocket
- **Pydantic** (2.11): 데이터 검증 및 설정 관리

### LLM 지원
- **Azure OpenAI**: 기업용 (권장)
- **OpenAI**: GPT-4, GPT-3.5
- **Anthropic**: Claude 3.5 Sonnet
- **Google**: Gemini 1.5 Pro
- **Ollama**: 로컬 LLM (Llama 3.2 등)

### 자동화 & 통합
- **MCP** (Model Context Protocol): Claude Desktop 연동
- **n8n**: 워크플로우 자동화
- **Docker**: 컨테이너화 및 배포

### 데이터 소스
- **NewsAPI**: 글로벌 뉴스
- **Naver News**: 한국 뉴스
- **YouTube Data API**: 비디오 분석

---

## 🏆 프로젝트 하이라이트

### 실전 에이전트 빌더로서의 역량 증명

✅ **멀티 스킬**
- 프롬프트 엔지니어링 (Few-Shot, 증거 기반)
- 시스템 설계 (LangGraph, 분산 실행)
- API 개발 (FastAPI, WebSocket)
- 자동화 (n8n, MCP)

✅ **실험과 실행 우선**
- 즉시 실행 가능한 코드
- 6가지 실전 사용 사례 문서화
- 샘플 데이터로 API 키 없이도 테스트 가능

✅ **프로덕션 레벨 품질**
- 에러 핸들링 (재시도, 부분 결과)
- 구조화된 로깅 (JSON, run_id 추적)
- 품질 메트릭 (커버리지, 사실성, 실행 가능성)
- 분산 실행 (4-워커 병렬 처리)

✅ **도구 활용 능력**
- n8n: 5가지 실전 워크플로우
- MCP: Claude Desktop 연동 (5분 설정)
- LangGraph: 공식 패턴 기반 구현
- FastAPI: 실시간 대시보드

---

## 📚 문서

| 문서 | 설명 | 소요 시간 |
|------|------|----------|
| [MCP 빠른 시작](automation/mcp/QUICKSTART.md) | Claude Desktop 연동 | 5분 |
| [n8n 실전 예제](automation/n8n/REAL_WORLD_EXAMPLES.md) | 5가지 자동화 워크플로우 | 10분 |
| [실전 사용 사례](docs/REAL_WORLD_USE_CASES.md) | 6가지 비즈니스 시나리오 | 15분 |
| [FastAPI 대시보드](agents/api/README.md) | API 문서 및 사용법 | 10분 |
| [시스템 프롬프트](agents/news_trend_agent/prompts/system.md) | 프롬프트 엔지니어링 | 20분 |

---

## 🤝 기여

이슈 및 풀 리퀘스트 환영합니다!

---

## 📝 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능

---

## 📧 연락처

- **GitHub**: [@rayvoidx](https://github.com/rayvoidx)
- **프로젝트**: [Automatic-Consumer-Trend-Analysis-Agent](https://github.com/rayvoidx/Automatic-Consumer-Trend-Analysis-Agent)

---

**⭐ 이 프로젝트가 도움이 되었다면 Star를 눌러주세요!**
