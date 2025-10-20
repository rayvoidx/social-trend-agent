# Quick Start Guide - 5분 안에 시작하기

> **목표**: 5분 내에 첫 번째 트렌드 분석 리포트 생성하기

---

## ⚡ 초고속 시작 (환경 변수 없이)

API 키가 없어도 샘플 데이터로 즉시 실행 가능합니다!

### 1️⃣ 저장소 클론 및 이동

```bash
git clone <repository-url>
cd Automatic-Consumer-Trend\ Analysis-Agent
```

### 2️⃣ 의존성 설치

```bash
# Python 의존성
pip install -r backend/requirements.txt

# 또는 필수 패키지만 (가벼운 설치)
pip install langgraph langchain-openai requests pydantic
```

### 3️⃣ 첫 번째 에이전트 실행

```bash
# 한글 뉴스 트렌드 분석
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "전기차" \
  --window 7d
```

**예상 출력:**
```
================================================================================
🔍 News Trend Agent
================================================================================
Query: 전기차
Time Window: 7d
Language: ko
Max Results: 20
================================================================================

[collect_node] query=전기차, time_window=7d
[search_news] query=전기차, time_window=7d, language=ko
⚠️  No API keys found, using sample data
[normalize_node] raw_items count=3
[analyze_node] normalized count=3
...

================================================================================
📄 REPORT
================================================================================

# 뉴스 트렌드 분석 리포트
...

✨ Agent execution completed successfully!
📁 Output: artifacts/news_trend_agent/[run-id].md
```

### 4️⃣ 결과 확인

```bash
# 최신 리포트 보기
ls -lt artifacts/news_trend_agent/ | head -3
cat artifacts/news_trend_agent/[run-id].md
```

---

## 🎯 다음 단계별 실행

### Step 1: 뉴스 트렌드 에이전트 (News Trend Agent)

#### 한글 뉴스 (샘플 데이터)
```bash
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "비건 간식" \
  --window 7d \
  --language ko
```

#### 영문 뉴스 (샘플 데이터)
```bash
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "vegan snacks" \
  --window 24h \
  --language en
```

#### JSON + MD 출력
```bash
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "AI 트렌드" \
  --emit md,json
```

---

### Step 2: 바이럴 비디오 에이전트 (Viral Video Agent)

#### YouTube 급상승
```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "trending topics" \
  --market KR \
  --platform youtube
```

#### 멀티 플랫폼 (YouTube + TikTok)
```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "K-pop" \
  --market KR \
  --platform youtube,tiktok
```

---

## 🔑 API 키 설정 (선택사항)

실제 데이터를 원한다면 API 키를 설정하세요.

### 1. 환경 변수 파일 생성

```bash
cp .env.example .env
```

### 2. API 키 입력

`.env` 파일을 열어 다음 항목을 설정:

```bash
# ===== 뉴스 API (선택) =====
NEWS_API_KEY=your_newsapi_key                    # newsapi.org
NAVER_CLIENT_ID=your_naver_client_id            # Naver Open API
NAVER_CLIENT_SECRET=your_naver_client_secret

# ===== 동영상 API (선택) =====
YOUTUBE_API_KEY=your_youtube_api_key            # YouTube Data API v3
TIKTOK_CONNECTOR_TOKEN=your_tiktok_token        # TikTok API

# ===== 알림 (선택) =====
SLACK_WEBHOOK_URL=https://hooks.slack.com/...   # Slack Webhook
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/...
```

### 3. API 키 발급 가이드

#### NewsAPI (영문 뉴스)
1. https://newsapi.org/ 접속
2. 무료 계정 생성 (개발용 충분)
3. API Key 복사 → `.env`의 `NEWS_API_KEY`에 입력

#### Naver Open API (한글 뉴스)
1. https://developers.naver.com/apps/#/register 접속
2. 애플리케이션 등록
3. 검색 API 선택
4. Client ID/Secret 복사 → `.env`에 입력

#### YouTube Data API v3
1. https://console.cloud.google.com/ 접속
2. 프로젝트 생성
3. "APIs & Services" → "Enable APIs" → "YouTube Data API v3"
4. "Credentials" → "Create API Key"
5. API Key 복사 → `.env`에 입력

---

## 🔔 알림 설정 (선택사항)

### Slack 알림

#### 1. Slack Webhook URL 생성
1. Slack Workspace 관리자 권한으로 로그인
2. https://api.slack.com/apps 접속
3. "Create New App" → "From scratch"
4. "Incoming Webhooks" 활성화
5. "Add New Webhook to Workspace"
6. 채널 선택 → Webhook URL 복사

#### 2. 에이전트 실행 시 알림 활성화
```bash
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "신제품 출시" \
  --notify slack
```

### n8n 자동화

#### 1. n8n 설치 (Docker)
```bash
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

#### 2. Webhook 노드 생성
1. http://localhost:5678 접속
2. 새 워크플로우 생성
3. "Webhook" 노드 추가
4. Webhook URL 복사 → `.env`의 `N8N_WEBHOOK_URL`

#### 3. 에이전트 → n8n 연동
```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "바이럴 트렌드" \
  --notify n8n
```

---

## 📊 출력 파일 위치

모든 산출물은 `artifacts/` 디렉토리에 저장됩니다:

```
artifacts/
├── news_trend_agent/
│   ├── [run-id-1].md            # 마크다운 리포트
│   ├── [run-id-1].json          # JSON 출력 (--emit json)
│   └── [run-id-1]_metrics.json  # 메트릭스
└── viral_video_agent/
    ├── [run-id-2].md
    ├── [run-id-2].json
    └── [run-id-2]_metrics.json
```

---

## 🐛 문제 해결

### 문제 1: `ModuleNotFoundError: No module named 'langgraph'`

**해결:**
```bash
pip install langgraph langchain-openai
```

### 문제 2: Permission Denied

**해결:**
```bash
chmod +x scripts/run_agent.py
```

### 문제 3: API 키 경고

```
⚠️  No API keys found, using sample data
```

**해결:** 정상입니다! 샘플 데이터로 계속 진행하거나, [API 키 설정](#-api-키-설정-선택사항) 참조.

### 문제 4: Python 버전

본 프로젝트는 **Python 3.11+** 필요합니다.

```bash
python --version  # 3.11 이상 확인
```

---

## ✅ 검증 체크리스트

- [ ] Python 3.11+ 설치 확인
- [ ] 의존성 설치 완료
- [ ] `scripts/run_agent.py` 실행 성공
- [ ] 마크다운 리포트 생성 확인 (`artifacts/` 디렉토리)
- [ ] 리포트에 감성 분석/키워드 포함 확인
- [ ] (선택) API 키 설정 및 실제 데이터 수집
- [ ] (선택) Slack/n8n 알림 전송 성공

---

## 🎓 다음에 할 일

### 1. 에이전트별 상세 가이드
- [news_trend_agent POW](../agents/news_trend_agent/POW.md)
- [viral_video_agent POW](../agents/viral_video_agent/POW.md)

### 2. 커스터마이징
- 시스템 프롬프트 수정: `agents/*/prompts/system.md`
- 도구 추가: `agents/*/tools.py`
- 그래프 로직 변경: `agents/*/graph.py`

### 3. 자동화
- [n8n 워크플로우](/automation/n8n/) - 크론 + 자동 실행
- [MCP 연동](/automation/mcp/) - 모델 컨텍스트 프로토콜

### 4. 개발 가이드
- [설계 문서](/docs/DESIGN_DOC.md)
- [사용 가이드](/USAGE_GUIDE.md)
- [Claude Code 작업 규칙](/CLAUDE_CODE_RULES.md)

---

## 💡 유용한 팁

### 팁 1: 복수 쿼리 자동화

```bash
# 여러 주제를 한번에 분석
for query in "전기차" "AI" "메타버스"; do
  python scripts/run_agent.py \
    --agent news_trend_agent \
    --query "$query" \
    --window 7d \
    --emit md
done
```

### 팁 2: 정기 실행 (cron)

```bash
# crontab -e
# 매일 오전 9시 실행
0 9 * * * cd /path/to/project && python scripts/run_agent.py --agent news_trend_agent --query "트렌드" --notify slack
```

### 팁 3: 리포트 아카이빙

```bash
# 월별로 아카이브
mkdir -p archives/2024-10
mv artifacts/news_trend_agent/*.md archives/2024-10/
```

---

## 🚀 성공!

축하합니다! 이제 소비자 트렌드 자동 분석 에이전트를 사용할 수 있습니다.

**질문이나 이슈가 있으면:**
- GitHub Issues 등록
- [프로젝트 문서](/docs/) 참조
- [상세 사용 가이드](/USAGE_GUIDE.md)

---

**⏱️ 소요 시간**: 실제로 5분 안에 완료하셨나요?
**다음 단계**: [POW 가이드](../agents/news_trend_agent/POW.md)로 더 깊이 있는 검증을 해보세요!
