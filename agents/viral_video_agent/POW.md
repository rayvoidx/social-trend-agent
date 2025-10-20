# Viral Video Agent - Proof of Work (POW)

> **목표**: 5-10분 내에 바이럴 비디오 에이전트가 정상 작동함을 검증

## ⏱️ 예상 소요 시간: 5-10분

---

## 📋 사전 준비

### 1. 환경 변수 설정 (선택)

API 키가 있다면 실시간 데이터를 수집할 수 있습니다. **없어도 샘플 데이터로 작동합니다.**

```bash
# .env 파일에 추가 (선택사항)
YOUTUBE_API_KEY=your_youtube_api_key              # YouTube Data API v3
TIKTOK_CONNECTOR_TOKEN=your_tiktok_token          # TikTok 공식/서드파티 커넥터
INSTAGRAM_CONNECTOR_TOKEN=your_instagram_token    # Instagram Graph API
```

### 2. 의존성 확인

```bash
# 프로젝트 루트에서
pip install -r backend/requirements.txt

# 또는 필수 패키지만
pip install langgraph langchain-openai requests pydantic numpy
```

---

## 🚀 검증 시나리오

### POW-1: YouTube 급상승 감지 (기본)

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "trending topics" \
  --market KR \
  --platform youtube \
  --window 7d
```

**예상 결과:**
- ✅ 비디오 데이터 수집: 5-20개 항목
- ✅ 급상승 신호 감지 (조회수/좋아요 스파이크)
- ✅ 토픽 클러스터링: 주요 주제 그룹핑
- ✅ 성공 요인 분석
- ✅ 마크다운 리포트 생성
- ✅ `artifacts/viral_video_agent/[run_id].md` 파일 생성

**성공 기준:**
```
✅ Markdown report saved: artifacts/viral_video_agent/xxx.md
✅ JSON output saved: artifacts/viral_video_agent/xxx.json
✅ Metrics saved: artifacts/viral_video_agent/xxx_metrics.json
✨ Agent execution completed successfully!
```

---

### POW-2: 멀티 플랫폼 분석 (YouTube + TikTok)

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "K-pop" \
  --market KR \
  --platform youtube,tiktok \
  --window 24h
```

**예상 결과:**
- YouTube와 TikTok 데이터 동시 수집
- 플랫폼별 바이럴 패턴 비교
- 크로스 플랫폼 트렌드 식별

---

### POW-3: 글로벌 시장 분석

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "viral challenges" \
  --market US \
  --platform youtube,tiktok \
  --window 7d \
  --emit md,json
```

**예상 결과:**
- 미국 시장 바이럴 트렌드
- 글로벌 vs 로컬 트렌드 차이
- JSON + MD 파일 모두 생성

---

### POW-4: 알림 연동 (고급)

```bash
# n8n/Slack 웹훅 설정 필요
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "신제품 리뷰" \
  --market KR \
  --platform youtube \
  --window 7d \
  --notify n8n,slack
```

**예상 결과:**
- ✅ 리포트 생성 + 파일 저장
- ✅ n8n 웹훅 호출 (급상승 알림)
- ✅ Slack 메시지 전송 (요약 + 주요 비디오)

---

## 🔍 출력 검증

### 1. 마크다운 리포트 확인

```bash
# 가장 최근 리포트 보기
ls -lt artifacts/viral_video_agent/ | head -5
cat artifacts/viral_video_agent/[최신-run-id].md
```

**필수 포함 항목:**
- ✅ 검색어, 시장, 플랫폼, 기간
- ✅ 급상승 비디오 Top 10 (조회수, 증가율)
- ✅ 바이럴 신호 분석 (스파이크 감지 결과)
- ✅ 토픽 클러스터 (주요 주제 그룹)
- ✅ 성공 요인 해설 (썸네일, 제목, 타이밍 등)
- ✅ 플랫폼별 비교 (멀티 플랫폼인 경우)
- ✅ 실행 권고안 (크리에이터/마케터용)
- ✅ 출처 링크 (비디오 URL)
- ✅ Run ID

### 2. 메트릭스 확인

```bash
cat artifacts/viral_video_agent/[run-id]_metrics.json
```

**예상 메트릭스:**
```json
{
  "run_id": "uuid-string",
  "timestamp": "20231019_143530",
  "metrics": {
    "spike_detected": 5,       // 급상승 감지된 비디오 수
    "avg_growth_rate": 245.3,  // 평균 증가율 (%)
    "coverage": 0.85,          // 데이터 수집율
    "actionability": 1.0       // 실행 가능한 인사이트 포함
  },
  "item_count": 18,
  "platforms": ["youtube", "tiktok"]
}
```

---

## 🐛 트러블슈팅

### 문제 1: ModuleNotFoundError (numpy)

```bash
# 해결:
pip install numpy
```

### 문제 2: API 키 없음 경고

```
⚠️  No API keys found, using sample data
```

**해결:** 정상입니다! 샘플 데이터로 계속 진행됩니다.

실제 API 키 설정:
```bash
# YouTube Data API v3
# 1. Google Cloud Console → API & Services → Enable APIs
# 2. YouTube Data API v3 활성화
# 3. Credentials → API Key 생성
# 4. .env에 추가: YOUTUBE_API_KEY=...
```

### 문제 3: 급상승 감지 없음

```
Spike detected: 0 videos
```

**원인:**
- 샘플 데이터는 임의 값 (실제 스파이크 없을 수 있음)
- 실제 API 사용 시 해결

**해결:** `--window 24h`로 짧은 기간 시도 또는 다른 query 사용

---

## ✅ 검증 체크리스트

- [ ] `scripts/run_agent.py` 실행 성공
- [ ] 마크다운 리포트 생성 확인
- [ ] 급상승 비디오 리스트 포함 확인
- [ ] 바이럴 신호 분석 결과 확인
- [ ] 토픽 클러스터 확인
- [ ] 성공 요인 해설 포함 확인
- [ ] 비디오 링크 포함 확인
- [ ] 메트릭스 파일 생성 확인
- [ ] Run ID 트래킹 확인
- [ ] (선택) 멀티 플랫폼 비교 결과 확인
- [ ] (선택) 웹훅 알림 전송 성공

---

## 📊 성능 벤치마크

| 항목 | 예상 시간 |
|------|----------|
| 비디오 데이터 수집 | 2-5초 |
| 데이터 정규화 | <1초 |
| 급상승 감지 (z-score) | 1-2초 |
| 토픽 클러스터링 | 2-3초 |
| 성공 요인 분석 | 3-5초 |
| 리포트 작성 | <1초 |
| **총 실행 시간** | **8-20초** |

---

## 🎯 활용 시나리오

### 시나리오 1: 신제품 런칭 모니터링

```bash
# 매일 크론으로 실행
0 9 * * * python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "우리제품명 리뷰" \
  --market KR \
  --platform youtube,tiktok \
  --notify slack
```

### 시나리오 2: 경쟁사 분석

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "경쟁사명" \
  --market KR,US,JP \
  --window 30d \
  --emit json
```

### 시나리오 3: 크리에이터 발굴

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "뷰티 인플루언서" \
  --market KR \
  --platform youtube,instagram \
  --window 7d
```

---

## 🧪 고급 설정

### 스파이크 임계값 조정

`agents/viral_video_agent/graph.py`에서:

```python
# 기본값: z-score > 2.0
spike_threshold: float = Field(2.0, description="Z-score threshold")

# 더 민감하게: 1.5
# 덜 민감하게: 3.0
```

### 플랫폼 우선순위

여러 플랫폼 사용 시 우선순위 조정 가능:

```bash
--platform youtube,tiktok,instagram
# → YouTube 우선 수집, TikTok/Instagram은 보조
```

---

## 📞 지원

문제가 발생하면:
1. `artifacts/viral_video_agent/` 디렉토리의 로그 확인
2. Python 버전 확인 (3.11+ 필요)
3. NumPy 설치 확인: `pip install numpy`
4. API 키 형식 확인 (불필요한 공백/따옴표 제거)

---

## 🎓 다음 단계

POW 검증 완료 후:

1. **README.md** - 에이전트 상세 문서 확인
2. **커스터마이징** - `prompts/system.md` 수정
3. **n8n 연동** - 자동 크론 + 알림 설정
4. **대시보드 연동** - JSON 출력 → BI 도구
5. **creator_onboarding_agent** - 크리에이터 심사 자동화 (선택)

---

**🎉 검증 완료하셨나요? 다음은 [n8n 워크플로우](/automation/n8n/)로 자동화해보세요!**
