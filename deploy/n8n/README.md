# n8n 워크플로우 자동화 가이드

> AI 트렌드 분석 에이전트를 n8n으로 자동화하는 방법

---

## 📦 제공되는 워크플로우

### 1. news_daily_report.json - 일일 뉴스 브리핑

**목적**: 매일 오전 9시에 지정된 키워드의 뉴스 트렌드를 분석하고, 결과를 Slack으로 알림하며 Google Sheets에 로그를 저장합니다.

**워크플로우 흐름**:
```
Daily Trigger (9 AM)
    ↓
Run News Trend Agent
    ↓
Webhook (Receive Report)
    ↓
Check Quality (coverage > 0.7?)
    ↓ Yes                    ↓ No
Send to Slack           Alert Low Quality
Log to Google Sheets
```

**입력**:
- `query`: 분석할 키워드 (예: "AI", "전기차", "경쟁브랜드")
- `time_window`: 분석 기간 (기본: 24h)

**출력**:
- Slack 메시지: 감성 비율, 키워드, 요약
- Google Sheets: 날짜, 쿼리, 감성 비율, 커버리지, 리포트 URL

**활용 시나리오**:
- 마케팅팀 아침 브리핑 자동화
- 경쟁사 뉴스 모니터링 대시보드
- 산업 트렌드 일일 추적

---

### 2. viral_spike_alert.json - 바이럴 급상승 알림

**목적**: 3시간마다 바이럴 비디오를 감지하고, 급상승 신호 발견 시 Slack/Email로 알림하며 Jira 티켓을 자동 생성합니다.

**워크플로우 흐름**:
```
Every 3 Hours
    ↓
Run Viral Agent
    ↓
Webhook (Receive Results)
    ↓
Spike Detected? (spike_detected > 0?)
    ↓ Yes                    ↓ No
Alert Team (Slack)        No Action
Email Marketing Team
Create Jira Ticket
```

**입력**:
- `query`: 분석할 키워드 (예: "trending topics", "K-pop")
- `market`: 시장 코드 (KR, US, JP)
- `platforms`: 플랫폼 (youtube, tiktok)

**출력**:
- Slack 알림: 급상승 비디오 정보, 성공 요인
- Email: 상세 분석 결과
- Jira 티켓: 마케팅팀 액션 아이템

**활용 시나리오**:
- 콘텐츠 마케팅팀 트렌드 포착
- 인플루언서 협업 기회 발굴
- 바이럴 챌린지 참여 타이밍 확보

---

## 🚀 설치 및 설정

### 1. n8n 실행

```bash
# Docker로 n8n 실행
docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n

# 또는 Docker Compose 사용
docker compose up -d n8n

# 브라우저에서 접속
# http://localhost:5678
```

### 2. 워크플로우 임포트

1. n8n 대시보드 접속 (http://localhost:5678)
2. 좌측 메뉴에서 **Workflows** 선택
3. **Import from File** 클릭
4. `news_daily_report.json` 또는 `viral_spike_alert.json` 선택
5. 임포트 완료

### 3. 환경 설정

#### Slack 연동
1. [Slack API](https://api.slack.com/apps)에서 앱 생성
2. **OAuth & Permissions**에서 `chat:write` 권한 추가
3. **Bot User OAuth Token** 복사
4. n8n Slack 노드에 토큰 설정

#### Google Sheets 연동
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Google Sheets API 활성화
3. 서비스 계정 생성 및 JSON 키 다운로드
4. n8n Google Sheets 노드에 credentials 설정
5. `YOUR_GOOGLE_SHEET_ID`를 실제 Sheet ID로 교체

#### Jira 연동 (viral_spike_alert.json용)
1. [Atlassian API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)에서 토큰 생성
2. n8n Jira 노드에 email + API token 설정
3. 프로젝트 키(`MARKETING`) 및 이슈 타입 확인

### 4. 워크플로우 활성화

1. 임포트된 워크플로우 열기
2. 우상단 **Active** 토글 활성화
3. 스케줄에 따라 자동 실행 시작

---

## 📊 마케터를 위한 자동화 예시

### 예시 1: 경쟁사 일일 모니터링

**시나리오**: 경쟁 브랜드 3개에 대한 뉴스를 매일 모니터링하고 Slack으로 브리핑 받기

**설정 방법**:
1. `news_daily_report.json` 임포트
2. Set 노드 추가하여 쿼리 목록 정의:
   ```json
   [
     {"query": "경쟁브랜드A"},
     {"query": "경쟁브랜드B"},
     {"query": "경쟁브랜드C"}
   ]
   ```
3. SplitInBatches 노드로 각 브랜드 순차 실행
4. Slack 채널을 `#competitor-watch`로 설정

**기대 결과**:
- 매일 오전 9시에 경쟁사 3개에 대한 뉴스 브리핑
- 감성 변화 추이 파악 (긍정 ↑/↓)
- 이슈 발생 시 빠른 대응 가능

---

### 예시 2: 캠페인 실시간 버즈 추적

**시나리오**: 신규 캠페인 런칭 후 소셜 반응을 실시간으로 추적

**설정 방법**:
1. Webhook Trigger로 변경 (스케줄 대신 수동 트리거)
2. HTTP Request 노드 추가:
   ```
   POST /n8n/agent/execute
   {
     "agent": "social_trend_agent",
     "query": "#캠페인해시태그",
     "sources": ["x", "instagram"]
   }
   ```
3. 결과를 Slack 채널 `#campaign-buzz`로 전송

**기대 결과**:
- 캠페인 런칭 직후부터 버즈 모니터링
- 해시태그 확산 추이 파악
- 부정 반응 발생 시 즉시 알림

---

### 예시 3: 콘텐츠 기획을 위한 바이럴 벤치마킹

**시나리오**: 매주 월요일에 지난 주 바이럴 비디오 분석 리포트 생성

**설정 방법**:
1. `viral_spike_alert.json` 수정
2. 스케줄을 `0 9 * * 1` (매주 월요일 오전 9시)로 변경
3. 쿼리를 브랜드 관련 키워드로 설정
4. 결과를 Notion 데이터베이스에 저장 (Notion 노드 추가)

**기대 결과**:
- 매주 월요일 바이럴 벤치마킹 리포트
- 성공 요인 분석 데이터 축적
- 콘텐츠 기획 인사이트 도출

---

### 예시 4: 위기 감지 자동화

**시나리오**: 부정적 뉴스 급증 시 즉시 알림

**설정 방법**:
1. `news_daily_report.json` 수정
2. 스케줄을 `0 */2 * * *` (2시간마다)로 변경
3. If 노드 조건 추가:
   ```
   {{ $json.sentiment.negative }} > 30
   ```
4. 조건 만족 시 `#crisis-alert` 채널로 알림
5. PagerDuty/Opsgenie 연동으로 담당자 호출

**기대 결과**:
- 부정 감성 30% 초과 시 즉시 알림
- 위기 상황 조기 감지
- 빠른 PR 대응 가능

---

## 📝 Slack 메시지 포맷 예시

### 뉴스 트렌드 리포트
```
🔍 *Daily News Trend Report* (2025-11-20)

*Query*: AI
*Items Analyzed*: 18
*Sentiment*: 😊 67% | 😐 22% | 😞 11%

*Top Keywords*: ChatGPT, 생성형AI, 자동화

*Summary*: AI 기술 발전에 대한 긍정적 반응이 지배적이며,
기업들의 도입 사례가 급증하고 있습니다.
일자리 대체 우려는 상대적으로 낮은 비중을 차지합니다.

[View Full Report](https://your-server.com/reports/run_abc123.md)
```

### 바이럴 급상승 알림
```
🔥 *Viral Spike Detected!* (2025-11-20 14:30)

*Platform*: youtube, tiktok
*Spikes Detected*: 5
*Avg Growth Rate*: 340%

*Top Viral Video*:
📹 신인 걸그룹 데뷔곡 챌린지
👁️ Views: 3,200,000 (+340%)
🔗 [Watch Now](https://youtube.com/watch?v=xxx)

*Success Factors*:
• Thumbnail: 눈에 띄는 포인트 컬러 사용
• Title Strategy: "챌린지" + "댄스" 키워드 조합
• Timing: 음원 발매 후 24시간 이내

[View Full Report](https://your-server.com/reports/viral_123.md)
```

---

## 🔧 커스터마이징

### 쿼리 파라미터 수정

Set 노드에서 쿼리 파라미터 변경:
```json
{
  "query": "원하는 키워드",
  "time_window": "7d",  // 24h, 7d, 30d
  "language": "ko",     // ko, en
  "max_results": 50
}
```

### 알림 채널 변경

Slack 노드의 `channel` 파라미터 수정:
```
#trend-alerts     →  #marketing-team
#viral-alerts     →  #content-creators
```

### 스케줄 변경

Schedule Trigger 노드의 cron 표현식 수정:
```
0 9 * * *        →  매일 오전 9시
0 */3 * * *      →  3시간마다
0 9 * * 1        →  매주 월요일 오전 9시
0 9,18 * * *     →  매일 오전 9시, 오후 6시
```

### 품질 임계값 조정

If 노드의 조건 수정:
```
coverage > 0.7    →  coverage > 0.8 (더 엄격)
coverage > 0.7    →  coverage > 0.5 (더 관대)
```

---

## 🔒 보안 권장사항

1. **API 키 관리**: n8n의 Credentials에 저장, 워크플로우에 직접 노출 금지
2. **Webhook 보안**: 인증 토큰 사용 또는 IP 제한 설정
3. **데이터 보존**: 민감 정보는 Google Sheets 대신 내부 DB 사용 고려
4. **권한 분리**: 알림 채널별로 접근 권한 설정

---

## ❓ 트러블슈팅

### 워크플로우가 실행되지 않음
- **원인**: 워크플로우가 비활성화 상태
- **해결**: 우상단 Active 토글 확인

### Slack 알림이 오지 않음
- **원인**: Bot Token 권한 부족 또는 채널 미가입
- **해결**: `chat:write` 권한 확인, 봇을 채널에 초대

### Google Sheets 에러
- **원인**: 서비스 계정에 시트 접근 권한 없음
- **해결**: 시트를 서비스 계정 이메일과 공유

### 에이전트 실행 실패
- **원인**: API 키 미설정 또는 서버 미실행
- **해결**: `.env` 파일 확인, `python main.py` 실행 상태 확인

---

## 📊 실험 메트릭 리포트 플로우

### 개요

A/B 테스트 실험의 메트릭을 자동으로 수집하여 Slack으로 주간 리포트를 전송하는 워크플로우입니다.

### 워크플로우 구조

```
Weekly Trigger (월요일 오전 9시)
    ↓
Fetch Experiment Metrics (API 호출)
    ↓
Calculate Statistics (통계 계산)
    ↓
Format Report (Slack 포맷)
    ↓
Send to Slack (#experiments 채널)
```

### 설정 방법

1. **n8n 워크플로우 생성**

```json
{
  "name": "Experiment Weekly Report",
  "nodes": [
    {
      "name": "Weekly Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "parameters": {
        "rule": {
          "interval": [{"field": "cronExpression", "expression": "0 9 * * 1"}]
        }
      }
    },
    {
      "name": "Fetch Metrics",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "{{ $env.API_URL }}/api/experiments/metrics",
        "method": "GET"
      }
    },
    {
      "name": "Send to Slack",
      "type": "n8n-nodes-base.slack",
      "parameters": {
        "channel": "#experiments",
        "text": "={{ $json.formatted_report }}"
      }
    }
  ]
}
```

2. **API 엔드포인트 구현 (필요시)**

```python
@app.get("/api/experiments/metrics")
async def get_experiment_metrics():
    """실험 메트릭 조회"""
    # 실험 데이터 조회 로직
    return {
        "experiments": [...],
        "formatted_report": "..."
    }
```

### Slack 리포트 포맷

```
📊 *실험 주간 리포트* ({{ $now.minus(7, 'days').format('YYYY-MM-DD') }} ~ {{ $now.format('YYYY-MM-DD') }})

*진행 중인 실험: {{ $json.running_count }}개*

---

{{ #each $json.experiments }}
*{{ this.id }}: {{ this.title }}*
• 상태: {{ this.status_emoji }} {{ this.status }}
• 데이터: {{ this.collected }} / {{ this.target }} ({{ this.progress }}%)
• 중간 결과:
  - Control: {{ this.control_value }} ({{ this.metric_name }})
  - Treatment: {{ this.treatment_value }} ({{ this.lift }})
  - 신뢰도: {{ this.confidence }}%
{{ /each }}

---

*이번 주 인사이트:*
{{ $json.insights }}

*다음 주 계획:*
{{ $json.next_actions }}
```

### 메트릭 계산 노드

Function 노드에서 통계 계산:

```javascript
// 신뢰도 계산
function calculateConfidence(controlData, treatmentData) {
  const controlMean = mean(controlData);
  const treatmentMean = mean(treatmentData);
  const pooledStdError = calculatePooledSE(controlData, treatmentData);
  const zScore = (treatmentMean - controlMean) / pooledStdError;
  const confidence = normalCDF(zScore) * 100;
  return confidence.toFixed(1);
}

// Lift 계산
function calculateLift(control, treatment) {
  const lift = ((treatment - control) / control) * 100;
  return lift > 0 ? `+${lift.toFixed(1)}%` : `${lift.toFixed(1)}%`;
}

// 상태 이모지
function getStatusEmoji(confidence, minSampleReached) {
  if (!minSampleReached) return '🟡'; // 진행 중
  if (confidence >= 95) return '🟢'; // 유의미
  if (confidence >= 90) return '🟠'; // 근접
  return '🔴'; // 불충분
}

return items.map(item => {
  const exp = item.json;
  return {
    ...exp,
    confidence: calculateConfidence(exp.control_data, exp.treatment_data),
    lift: calculateLift(exp.control_value, exp.treatment_value),
    status_emoji: getStatusEmoji(exp.confidence, exp.sample_reached)
  };
});
```

### 알림 조건 설정

특정 조건에서 추가 알림:

```javascript
// 조기 종료 가능 조건 (신뢰도 99% 초과)
if (confidence > 99 && sampleSize > minSample * 0.5) {
  return {
    alert: true,
    message: `🎉 EXP-${id} 조기 종료 가능! 신뢰도 ${confidence}%`
  };
}

// 저조한 성과 경고
if (lift < -10 && sampleSize > minSample * 0.3) {
  return {
    alert: true,
    message: `⚠️ EXP-${id} Treatment 저조 (${lift}). 검토 필요.`
  };
}
```

### 데이터 소스 연동

실험 데이터를 다양한 소스에서 가져올 수 있습니다:

**1. Google Sheets**
```
실험별 스프레드시트에서 일일 메트릭 수집
```

**2. PostgreSQL**
```sql
SELECT
  experiment_id,
  variant,
  COUNT(*) as samples,
  AVG(converted::int) as conversion_rate
FROM experiment_events
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY experiment_id, variant
```

**3. Custom API**
```
내부 분석 시스템 API에서 실험 결과 조회
```

### 실험 완료 후 자동화

실험 완료 시 자동 처리:

```json
{
  "name": "Experiment Completed",
  "nodes": [
    {
      "name": "Check Completion",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.status }}",
              "value2": "completed"
            }
          ]
        }
      }
    },
    {
      "name": "Archive Results",
      "type": "n8n-nodes-base.googleSheets",
      "parameters": {
        "operation": "append",
        "sheetName": "Completed Experiments"
      }
    },
    {
      "name": "Notify Team",
      "type": "n8n-nodes-base.slack",
      "parameters": {
        "channel": "#experiments",
        "text": "✅ *실험 완료: {{ $json.title }}*\n\nWinner: {{ $json.winner }}\nLift: {{ $json.final_lift }}\n결정: {{ $json.decision }}"
      }
    },
    {
      "name": "Create Follow-up Task",
      "type": "n8n-nodes-base.jira",
      "parameters": {
        "summary": "실험 결과 적용: {{ $json.title }}",
        "description": "Winner: {{ $json.winner }}\n\n{{ $json.implementation_notes }}"
      }
    }
  ]
}
```

---

## 📚 참고 자료

- [n8n 공식 문서](https://docs.n8n.io/)
- [Slack API 문서](https://api.slack.com/docs)
- [Google Sheets API 문서](https://developers.google.com/sheets/api)
- [Jira REST API 문서](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
- [docs/experiments.md](../../docs/experiments.md) - 실험 정의 템플릿

---

## 📧 문의

워크플로우 관련 문의는 [GitHub Issues](https://github.com/rayvoidx/social-trend-agent/issues)에 등록해주세요.
