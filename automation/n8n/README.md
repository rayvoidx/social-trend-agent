# n8n 워크플로우 가이드

> 트렌드 분석 에이전트를 n8n으로 자동화하는 워크플로우 예제

---

## 📋 포함된 워크플로우

### 1. news_daily_report.json
**목적**: 매일 정해진 시간에 뉴스 트렌드 리포트 생성 및 배포

**스케줄**: 매일 오전 9시

**워크플로우**:
```
Cron Trigger (9 AM)
  → Run News Trend Agent
  → Webhook (Receive Report)
  → Quality Check
  → [High Quality] Send to Slack + Log to Google Sheets
  → [Low Quality] Alert Low Quality
```

**알림 채널**:
- Slack (#trend-alerts)
- Google Sheets (로그 저장)
- Email (선택)

---

### 2. viral_spike_alert.json
**목적**: 바이럴 급상승 신호 실시간 감지 및 즉시 알림

**스케줄**: 3시간마다

**워크플로우**:
```
Cron Trigger (Every 3h)
  → Run Viral Video Agent
  → Webhook (Receive Results)
  → Spike Detected?
  → [YES] Alert Team + Email Marketing + Create Jira Ticket
  → [NO] No Action
```

**알림 채널**:
- Slack (#viral-alerts)
- Email (marketing@company.com)
- Jira (자동 티켓 생성)

---

## 🚀 설치 및 사용

### 1. n8n 설치

#### Docker (권장)
```bash
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  -e N8N_BASIC_AUTH_ACTIVE=true \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=your_password \
  n8nio/n8n
```

#### npm
```bash
npm install n8n -g
n8n start
```

접속: http://localhost:5678

---

### 2. 워크플로우 가져오기

1. n8n 웹 UI 접속
2. 상단 메뉴 → **Workflows**
3. **Import from File** 클릭
4. `news_daily_report.json` 또는 `viral_spike_alert.json` 선택
5. Import 완료

---

### 3. 워크플로우 설정

#### 3.1 에이전트 실행 경로 확인

**Execute Command** 노드에서:
```bash
# 프로젝트 경로 확인
cd /path/to/Automatic-Consumer-Trend-Analysis-Agent

# 에이전트 실행 명령 테스트
python scripts/run_agent.py --agent news_trend_agent --query "test" --window 24h --notify n8n
```

#### 3.2 웹훅 URL 설정

1. **Webhook** 노드 클릭
2. **Production URL** 복사 (예: `https://your-n8n.com/webhook/news-report`)
3. `.env` 파일에 추가:
```bash
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/news-report
```

#### 3.3 Slack 연동

1. n8n에서 **Credentials** → **Create New**
2. **Slack** 선택
3. Slack Webhook URL 입력 (또는 OAuth 인증)
4. **Send to Slack** 노드에서 해당 Credential 선택

**Slack Webhook URL 발급:**
1. https://api.slack.com/apps 접속
2. **Create New App** → **From scratch**
3. **Incoming Webhooks** 활성화
4. **Add New Webhook to Workspace**
5. 채널 선택 (#trend-alerts, #viral-alerts)
6. Webhook URL 복사

#### 3.4 Google Sheets 연동 (선택)

1. n8n에서 **Credentials** → **Create New**
2. **Google Sheets** 선택
3. Google OAuth 인증
4. **Log to Google Sheets** 노드에서:
   - **Document ID**: Google Sheets URL의 ID 부분
   - **Sheet Name**: 시트 이름 (예: "Trend Reports")

#### 3.5 Email 설정 (선택)

1. **Email Send** 노드에서:
   - SMTP 서버 설정 (Gmail, SendGrid 등)
   - 발신자/수신자 이메일

#### 3.6 Jira 연동 (선택)

1. n8n에서 **Credentials** → **Create New**
2. **Jira** 선택
3. Jira 도메인, API 토큰 입력
4. **Create Jira Ticket** 노드에서:
   - Project: 프로젝트 키 (예: MARKETING)
   - Issue Type: Task, Bug 등

---

### 4. 워크플로우 활성화

1. 우측 상단 **Inactive** 토글 클릭 → **Active**
2. 크론 스케줄 확인 (Daily Trigger: 9 AM, Viral: Every 3h)
3. 첫 실행 대기 또는 **Execute Workflow** 수동 실행

---

## 🧪 테스트

### 수동 실행

1. 워크플로우 열기
2. 좌측 **Execute Workflow** 클릭
3. 각 노드 결과 확인

### 웹훅 테스트

```bash
# 테스트 페이로드 전송
curl -X POST https://your-n8n.com/webhook/news-report \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "test-123",
    "query": "전기차",
    "item_count": 15,
    "sentiment": {"positive": 67, "neutral": 28, "negative": 5},
    "keywords": ["전기차", "배터리", "충전"],
    "summary": "긍정적 트렌드",
    "metrics": {"coverage": 0.9},
    "report_url": "http://localhost:8080/artifacts/test-123.md"
  }'
```

---

## ⚙️ 커스터마이징

### 크론 스케줄 변경

**Schedule Trigger** 노드에서:
```
0 9 * * *     # 매일 오전 9시
0 */3 * * *   # 3시간마다
0 12 * * 1    # 매주 월요일 정오
0 0 1 * *     # 매월 1일 자정
```

### 쿼리 동적 변경

**Execute Command** 노드에서:
```bash
# 환경 변수 사용
python scripts/run_agent.py --agent news_trend_agent --query "$TREND_QUERY" --window 24h

# n8n 변수 사용
python scripts/run_agent.py --agent news_trend_agent --query "{{ $node['Set Query'].json['query'] }}" --window 24h
```

### 조건 로직 추가

**IF** 노드로 분기:
- Coverage < 0.7 → 경고 알림
- Spike > 10 → 긴급 알림 + 이메일
- Negative > 50% → 부정 트렌드 리포트

---

## 🐛 문제 해결

### 문제 1: 워크플로우가 실행되지 않음

**확인 사항:**
- n8n이 실행 중인지 확인 (`docker ps` 또는 `ps aux | grep n8n`)
- 워크플로우가 Active 상태인지 확인
- 크론 스케줄이 올바른지 확인

### 문제 2: Execute Command 실패

**원인:**
- Python 경로 불일치
- 프로젝트 경로 불일치
- 권한 문제

**해결:**
```bash
# Execute Command 노드에서 절대 경로 사용
cd /absolute/path/to/project && python scripts/run_agent.py ...

# 또는 Shell Script 생성
#!/bin/bash
cd /path/to/project
source venv/bin/activate  # 가상환경 사용 시
python scripts/run_agent.py "$@"
```

### 문제 3: Webhook이 응답하지 않음

**확인:**
- 웹훅 URL이 `.env`에 정확히 설정되었는지
- n8n이 외부에서 접근 가능한지 (포트, 방화벽)
- 웹훅 노드가 **Production** 모드인지

**해결:**
```bash
# n8n을 공개적으로 노출 (개발용)
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -e WEBHOOK_URL=https://your-domain.com \
  n8nio/n8n

# 또는 ngrok 사용 (테스트용)
ngrok http 5678
# Webhook URL: https://xxxx.ngrok.io/webhook/news-report
```

### 문제 4: Slack 알림 실패

**원인:**
- Webhook URL 만료
- Credential 미설정
- 채널 권한 없음

**해결:**
1. Slack Webhook URL 재발급
2. n8n Credential 재설정
3. 봇을 채널에 초대 (`/invite @n8n-bot`)

---

## 📊 모니터링

### n8n 실행 로그

```bash
# Docker
docker logs n8n -f

# npm
tail -f ~/.n8n/n8n.log
```

### 실행 기록 확인

n8n 웹 UI → **Executions** 탭:
- 성공/실패 횟수
- 각 노드별 실행 시간
- 에러 메시지

---

## 🎯 고급 활용

### 1. 멀티 에이전트 체인

```
News Trend Agent
  → 긍정 트렌드 감지
  → Viral Video Agent 트리거
  → 관련 바이럴 비디오 검색
  → 통합 리포트 생성
```

### 2. 자동 리트윗/공유

급상승 비디오 감지 → Twitter/LinkedIn 자동 포스팅

### 3. BI 도구 연동

Google Sheets → Looker Studio/Tableau 자동 업데이트

---

## 📚 참고 자료

- [n8n 공식 문서](https://docs.n8n.io/)
- [n8n 크론 표현식](https://crontab.guru/)
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Jira REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)

---

**버전**: 1.0.0
**최종 업데이트**: 2024-10-19
**유지보수자**: Automation Team
