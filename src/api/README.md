# FastAPI 서버 가이드

LangGraph 에이전트를 REST API 및 WebSocket으로 제공하는 FastAPI 서버입니다.

## 🚀 빠른 시작

### 서버 실행

```bash
# 개발 모드
uvicorn agents.api.dashboard:app --reload --port 8000

# 프로덕션 모드
uvicorn agents.api.dashboard:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker로 실행

```bash
docker compose up -d
```

## 📡 API 엔드포인트

### 1. 헬스 체크

```bash
GET /health
```

**응답**:
```json
{
  "status": "ok",
  "timestamp": "2024-11-02T12:00:00Z"
}
```

### 2. 동기 에이전트 실행

```bash
POST /api/execute
Content-Type: application/json

{
  "agentName": "news_trend_agent",
  "query": "AI",
  "params": {
    "timeWindow": "7d",
    "language": "ko",
    "maxResults": 20
  }
}
```

**응답**:
```json
{
  "status": "success",
  "run_id": "uuid-here",
  "query": "AI",
  "analysis": {
    "sentiment": {...},
    "keywords": {...},
    "summary": "..."
  },
  "report_md": "# 뉴스 트렌드 분석...",
  "metrics": {
    "coverage": 0.9,
    "factuality": 1.0,
    "actionability": 1.0
  }
}
```

### 3. 비동기 태스크 제출

```bash
POST /api/tasks
Content-Type: application/json

{
  "agentName": "news_trend_agent",
  "query": "AI",
  "params": {"timeWindow": "7d"}
}
```

**응답**:
```json
{
  "task_id": "task-uuid",
  "status": "submitted",
  "message": "Task submitted successfully"
}
```

### 4. 태스크 상태 조회

```bash
GET /api/tasks/{task_id}
```

**응답**:
```json
{
  "task_id": "task-uuid",
  "status": "completed|running|failed",
  "result": {...},
  "created_at": "2024-11-02T12:00:00Z",
  "completed_at": "2024-11-02T12:00:15Z"
}
```

### 5. 대시보드 요약

```bash
GET /api/dashboard/summary
```

**응답**:
```json
{
  "total_tasks": 100,
  "completed_tasks": 95,
  "failed_tasks": 2,
  "running_tasks": 3,
  "avg_execution_time": 12.5,
  "recent_tasks": [...]
}
```

## 🔌 WebSocket 스트리밍

### 연결

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/stream/{task_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Progress:', data);
};
```

### 메시지 형식

```json
{
  "event": "node_start|node_end|progress|complete|error",
  "node": "collect|normalize|analyze|...",
  "data": {...},
  "timestamp": "2024-11-02T12:00:00Z"
}
```

## 📊 Server-Sent Events (SSE)

### 연결

```javascript
const eventSource = new EventSource('http://localhost:8000/sse/stream/{task_id}');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data);
};
```

## 🔗 n8n 연동

### n8n 웹훅 엔드포인트

```bash
POST /api/n8n/webhook
Content-Type: application/json

{
  "action": "analyze",
  "query": "AI",
  "timeWindow": "7d",
  "notificationUrl": "https://your-n8n-instance/webhook/..."
}
```

## 🛠️ 설정

### 환경 변수

```bash
# API 서버 포트
API_PORT=8000

# CORS 설정
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# 최대 워커 수
MAX_WORKERS=4

# 로그 레벨
LOG_LEVEL=INFO
```

## 📝 사용 예시

### Python (requests)

```python
import requests

response = requests.post(
    "http://localhost:8000/api/execute",
    json={
        "agentName": "news_trend_agent",
        "query": "AI",
        "params": {"timeWindow": "7d"}
    }
)

result = response.json()
print(result["analysis"]["summary"])
```

### cURL

```bash
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agentName": "news_trend_agent",
    "query": "AI",
    "params": {"timeWindow": "7d"}
  }'
```

### JavaScript (fetch)

```javascript
const response = await fetch('http://localhost:8000/api/execute', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    agentName: 'news_trend_agent',
    query: 'AI',
    params: { timeWindow: '7d' }
  })
});

const result = await response.json();
console.log(result.analysis.summary);
```

## 🔒 보안

### API 키 인증 (향후 추가 예정)

```bash
POST /api/execute
Authorization: Bearer your-api-key
```

## 📈 모니터링

### 메트릭 엔드포인트

```bash
GET /metrics
```

Prometheus 형식의 메트릭 제공:
- `agent_execution_total`: 총 실행 횟수
- `agent_execution_duration_seconds`: 실행 시간
- `agent_execution_errors_total`: 에러 횟수

## 🐛 디버깅

### 로그 확인

```bash
# Docker
docker compose logs -f

# 로컬
tail -f logs/agent.log
```

### 상세 로깅 활성화

```bash
LOG_LEVEL=DEBUG uvicorn agents.api.dashboard:app --reload
```

## 🚨 에러 처리

### 에러 응답 형식

```json
{
  "error": "Error message",
  "detail": "Detailed error information",
  "status_code": 500
}
```

### 일반적인 에러

- `400 Bad Request`: 잘못된 요청 파라미터
- `404 Not Found`: 태스크 ID를 찾을 수 없음
- `500 Internal Server Error`: 서버 내부 에러
- `503 Service Unavailable`: LLM API 연결 실패

## 📚 추가 정보

- **LangGraph 문서**: [langgraph.com](https://langchain-ai.github.io/langgraph/)
- **FastAPI 문서**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)
- **프로젝트 README**: [../../../README.md](../../../README.md)
