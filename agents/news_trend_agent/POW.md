# News Trend Agent - Proof of Work (POW)

> **목표**: 5-10분 내에 뉴스 트렌드 에이전트가 정상 작동함을 검증

## ⏱️ 예상 소요 시간: 5-10분

---

## 📋 사전 준비

### 1. 환경 변수 설정 (선택)

API 키가 있다면 더 풍부한 데이터를 얻을 수 있습니다. **없어도 샘플 데이터로 작동합니다.**

```bash
# .env 파일에 추가 (선택사항)
NEWS_API_KEY=your_news_api_key          # NewsAPI.org (영문 뉴스)
NAVER_CLIENT_ID=your_naver_client_id    # Naver Open API (한글 뉴스)
NAVER_CLIENT_SECRET=your_naver_secret
```

### 2. 의존성 확인

```bash
# 프로젝트 루트에서
pip install -r backend/requirements.txt

# 또는 필수 패키지만
pip install langgraph langchain-openai requests pydantic
```

---

## 🚀 검증 시나리오

### POW-1: 기본 실행 (한글 뉴스)

```bash
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "전기차" \
  --window 7d \
  --language ko
```

**예상 결과:**
- ✅ 뉴스 수집: 3-20개 항목
- ✅ 감성 분석: 긍정/중립/부정 비율
- ✅ 키워드 추출: Top 10-20 키워드
- ✅ 마크다운 리포트 생성
- ✅ `artifacts/news_trend_agent/[run_id].md` 파일 생성

**성공 기준:**
```
✅ Markdown report saved: artifacts/news_trend_agent/xxx.md
✅ JSON output saved: artifacts/news_trend_agent/xxx.json
✅ Metrics saved: artifacts/news_trend_agent/xxx_metrics.json
✨ Agent execution completed successfully!
```

---

### POW-2: 영문 뉴스 분석

```bash
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "electric vehicles" \
  --window 24h \
  --language en \
  --max-results 15
```

**예상 결과:**
- API 키가 있으면 실시간 영문 뉴스
- 없으면 샘플 데이터로 대체
- 영문 키워드 추출 및 분석

---

### POW-3: JSON 출력 + 알림 전송 (고급)

```bash
# n8n/Slack 웹훅 설정 필요
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "AI 트렌드" \
  --window 7d \
  --emit md,json \
  --notify n8n,slack
```

**예상 결과:**
- ✅ MD + JSON 파일 모두 생성
- ✅ n8n 웹훅 호출 (설정된 경우)
- ✅ Slack 메시지 전송 (설정된 경우)

---

## 🔍 출력 검증

### 1. 마크다운 리포트 확인

```bash
# 가장 최근 리포트 보기
ls -lt artifacts/news_trend_agent/ | head -5
cat artifacts/news_trend_agent/[최신-run-id].md
```

**필수 포함 항목:**
- ✅ 검색어, 기간, 언어
- ✅ 감성 분석 (긍정/중립/부정 %)
- ✅ 핵심 키워드 Top 10
- ✅ 주요 인사이트 (실행 권고안 포함)
- ✅ 주요 뉴스 Top 5 (출처 링크 포함)
- ✅ 경고 문구 (AI 생성, 사실 확인 필요)
- ✅ Run ID

### 2. 메트릭스 확인

```bash
cat artifacts/news_trend_agent/[run-id]_metrics.json
```

**예상 메트릭스:**
```json
{
  "run_id": "uuid-string",
  "timestamp": "20231019_143022",
  "metrics": {
    "coverage": 0.75,      // 수집율 (0-1)
    "factuality": 1.0,     // 출처 신뢰도
    "actionability": 1.0   // 실행 가능한 인사이트 포함 여부
  },
  "item_count": 15
}
```

---

## 🐛 트러블슈팅

### 문제 1: ModuleNotFoundError

```bash
# 해결:
cd /path/to/project
pip install -r backend/requirements.txt
```

### 문제 2: API 키 없음 경고

```
⚠️  No API keys found, using sample data
```

**해결:** 정상입니다! 샘플 데이터로 계속 진행됩니다.

### 문제 3: 웹훅 전송 실패

```
❌ Failed to send n8n notification: ...
```

**해결:**
- `.env`에 `N8N_WEBHOOK_URL` 또는 `SLACK_WEBHOOK_URL` 확인
- 웹훅 URL이 유효한지 확인
- 또는 `--notify` 옵션 제거하고 실행

---

## ✅ 검증 체크리스트

- [ ] `scripts/run_agent.py` 실행 성공
- [ ] 마크다운 리포트 생성 확인
- [ ] 감성 분석 결과 포함 확인
- [ ] 키워드 추출 결과 포함 확인
- [ ] 출처 링크 Top 5 포함 확인
- [ ] 메트릭스 파일 생성 확인
- [ ] Run ID 트래킹 확인
- [ ] (선택) 웹훅 알림 전송 성공

---

## 📊 성능 벤치마크

| 항목 | 예상 시간 |
|------|----------|
| 뉴스 수집 | 1-3초 |
| 데이터 정규화 | <1초 |
| 감성 분석 | 1-2초 |
| 키워드 추출 | 1-2초 |
| 요약 생성 | 2-5초 |
| 리포트 작성 | <1초 |
| **총 실행 시간** | **5-15초** |

---

## 🎯 다음 단계

POW 검증 완료 후:

1. **README.md** - 에이전트 상세 문서 확인
2. **커스터마이징** - `prompts/system.md` 수정
3. **n8n 연동** - `/automation/n8n/` 워크플로우 설정
4. **프로덕션 배포** - API 키 설정 및 스케줄링

---

## 📞 지원

문제가 발생하면:
1. `artifacts/` 디렉토리의 로그 확인
2. Python 버전 확인 (3.11+ 필요)
3. 의존성 재설치: `pip install -r backend/requirements.txt --force-reinstall`

---

**🎉 검증 완료하셨나요? 다음은 [viral_video_agent POW](../viral_video_agent/POW.md)를 확인해보세요!**
