# Viral Video Agent

> YouTube, TikTok, Instagram에서 급상승하는 콘텐츠를 감지하고 성공 요인을 분석하는 바이럴 비디오 전문 에이전트

---

## 📌 개요

Viral Video Agent는 다양한 동영상 플랫폼에서 바이럴 신호를 자동으로 감지하고, 통계적 방법(z-score)과 토픽 클러스터링을 통해 크리에이터와 마케터에게 실행 가능한 인사이트를 제공합니다.

### 주요 기능
- ✅ **멀티 플랫폼 지원**: YouTube, TikTok, Instagram
- ✅ **급상승 감지**: z-score 기반 통계적 스파이크 탐지
- ✅ **토픽 클러스터링**: 유사 콘텐츠 자동 그룹핑
- ✅ **성공 요인 분석**: 썸네일, 제목, 타이밍 등 체계적 분해
- ✅ **크로스 플랫폼 비교**: 플랫폼별 특성 및 시너지 분석
- ✅ **마크다운 리포트**: 비디오 링크 포함 완전한 문서
- ✅ **알림 연동**: n8n, Slack 웹훅 지원

---

## 🚀 빠른 시작

### 기본 실행 (샘플 데이터)

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "trending topics" \
  --market KR \
  --platform youtube
```

### 멀티 플랫폼 분석

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "K-pop" \
  --market KR \
  --platform youtube,tiktok \
  --window 7d
```

### API 키 사용 (실제 데이터)

```bash
# .env 파일 설정
YOUTUBE_API_KEY=your_youtube_key
TIKTOK_CONNECTOR_TOKEN=your_tiktok_token

# 실행
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "viral challenges" \
  --market US \
  --platform youtube,tiktok
```

---

## 🛠️ 아키텍처

### LangGraph 워크플로우

```
┌─────────┐
│ collect │ ─── 비디오 데이터 수집 (YouTube, TikTok, Instagram)
└────┬────┘
     │
┌────▼──────┐
│ normalize │ ─── 데이터 정규화 (조회수, 좋아요, 공유 등)
└────┬──────┘
     │
┌────▼────┐
│ analyze │ ─── 급상승 감지 (z-score) + 토픽 클러스터링
└────┬────┘
     │
┌────▼──────┐
│ summarize │ ─── 성공 요인 분석 (썸네일, 제목, 타이밍)
└────┬──────┘
     │
┌────▼────┐
│ report  │ ─── 마크다운 리포트 생성
└────┬────┘
     │
┌────▼────┐
│ notify  │ ─── n8n/Slack 알림
└─────────┘
```

### 상태 스키마

```python
class ViralAgentState(AgentState):
    query: str                    # 검색어/토픽
    market: str                   # 시장 (KR, US, JP 등)
    platforms: List[str]          # 플랫폼 리스트
    time_window: str              # 기간 (24h, 7d, 30d)
    spike_threshold: float        # 급상승 임계값 (기본: 2.0)

    raw_items: List[Dict]         # 원본 비디오 데이터
    normalized: List[Dict]        # 정규화된 데이터
    analysis: Dict                # 분석 결과 (스파이크, 클러스터)
    report_md: str                # 최종 리포트
    metrics: Dict                 # 품질 메트릭스
    run_id: str                   # 실행 ID
```

---

## 🔧 주요 도구 (Tools)

### 1. fetch_video_stats
비디오 통계 수집

**시그니처:**
```python
def fetch_video_stats(
    query: str,
    platforms: List[str],
    market: str = "KR",
    time_window: str = "7d"
) -> List[Dict[str, Any]]
```

**동작:**
- YouTube Data API v3
- TikTok Research API (또는 공식 커넥터)
- Instagram Graph API
- API 키 없으면 샘플 데이터로 자동 전환

**출력 예시:**
```json
[
  {
    "platform": "youtube",
    "video_id": "abc123",
    "title": "신인 걸그룹 데뷔 무대",
    "channel": "MnetTV",
    "views": 3245820,
    "likes": 89234,
    "comments": 15234,
    "shares": 4521,
    "published_at": "2024-10-17T10:00:00Z",
    "url": "https://youtube.com/watch?v=abc123",
    "thumbnail": "https://..."
  }
]
```

---

### 2. detect_spike
급상승 신호 감지

**시그니처:**
```python
def detect_spike(
    timeseries: List[Dict[str, Any]],
    threshold: float = 2.0
) -> Dict[str, Any]
```

**방법:**
- **z-score 기반**: `z = (x - μ) / σ`
- 임계값 기본값: 2.0 (평균에서 2 표준편차 이상)
- 급상승 판정: z-score > threshold

**출력 예시:**
```json
{
  "spike_detected": [
    {
      "video_id": "abc123",
      "z_score": 3.8,
      "growth_rate": 340.5,
      "status": "급상승"
    }
  ],
  "total_spikes": 5,
  "avg_growth_rate": 245.3
}
```

**z-score 해석:**
- `z > 3.0`: 매우 강한 급상승
- `2.0 < z ≤ 3.0`: 급상승
- `1.5 < z ≤ 2.0`: 주목 필요
- `z ≤ 1.5`: 정상 범위

---

### 3. topic_cluster
토픽 클러스터링

**시그니처:**
```python
def topic_cluster(
    texts: List[str],
    n_clusters: int = 3
) -> Dict[str, Any]
```

**방법:**
- 미니배치 TF-IDF + KMeans (소규모)
- 또는 LLM 기반 토픽 추출 (대규모)

**출력 예시:**
```json
{
  "clusters": [
    {
      "cluster_id": 0,
      "name": "공식 콘텐츠",
      "video_count": 8,
      "keywords": ["데뷔", "무대", "직캠"],
      "total_views": 8500000,
      "representative_videos": ["abc123", "def456"]
    },
    {
      "cluster_id": 1,
      "name": "챌린지/커버",
      "video_count": 10,
      "keywords": ["챌린지", "커버댄스", "따라하기"],
      "total_views": 12300000,
      "representative_videos": ["ghi789"]
    }
  ]
}
```

---

### 4. analyze_success_factors
성공 요인 분석

**시그니처:**
```python
def analyze_success_factors(
    video: Dict[str, Any]
) -> Dict[str, Any]
```

**분석 항목:**
1. **썸네일**: 색상, 구도, 텍스트 오버레이
2. **제목 전략**: 키워드, 감정, 호기심 유발 요소
3. **타이밍**: 업로드 시간, 트렌드 편승 여부
4. **콘텐츠 품질**: 편집, 길이, 참여 유도
5. **크리에이터**: 팔로워 수, 기존 영향력

**출력 예시:**
```json
{
  "thumbnail": {
    "colors": ["고채도 빨강", "파랑"],
    "emotion": "놀람",
    "text_overlay": true
  },
  "title": {
    "keywords": ["신인", "걸그룹", "데뷔"],
    "strategy": "호기심 유발",
    "emotion": "기대감"
  },
  "timing": {
    "upload_time": "18:00 (최적)",
    "trend_match": true,
    "seasonality": "음원 차트 1위 시점"
  },
  "engagement": {
    "like_ratio": 0.982,
    "comment_rate": 0.047,
    "avg_watch_time": "8:32"
  }
}
```

---

## 📊 출력 형식

### 마크다운 리포트 구조

```markdown
# 바이럴 비디오 분석 리포트

**검색어**: [query]
**시장**: [market]
**플랫폼**: [platforms]
**기간**: [time_window]
**분석 비디오 수**: [count]

---

## 🔥 급상승 비디오 Top 10

### 1. [비디오 제목]
**플랫폼**: YouTube
**채널**: [채널명] (구독자 XXK)
**조회수**: XXX,XXX (+XXX% ↗️)
**링크**: [URL]

**급상승 신호**:
- z-score: X.X
- 좋아요 비율: XX%
- 댓글 참여도: [높음/중간/낮음]

**성공 요인**:
- 썸네일: [특징]
- 제목: [전략]
- 콘텐츠: [유형]
- 타이밍: [분석]

---

## 📊 바이럴 신호 분석
- 급상승 감지: X개
- 평균 증가율: XXX%
- 스파이크 패턴: [분석]

---

## 🎯 ��픽 클러스터
### 클러스터 1: "[주제명]"
- 비디오 수: X개
- 총 조회수: XXXm
- 핵심 키워드: [키워드들]

---

## 💡 플랫폼별 비교
[크로스 플랫폼 시너지 분석]

---

## 🚀 실행 권고안
### 크리에이터용
[즉시 실행 / 콘텐츠 전략 / 장기 최적화]

### 마케터용
[인플루언서 협업 / 캠페인 타이밍 / 플랫폼 선택]

---

⚠️ **주의**: 플랫폼 정책과 저작권을 준수하세요.
**Run ID**: `[run_id]`
```

### 메트릭스 파일 (JSON)

```json
{
  "run_id": "uuid",
  "timestamp": "20241019_150000",
  "metrics": {
    "spike_detected": 10,
    "avg_growth_rate": 245.3,
    "coverage": 0.85,
    "actionability": 1.0
  },
  "item_count": 25,
  "platforms": ["youtube", "tiktok"],
  "cluster_analysis": {
    "total_clusters": 3,
    "clusters": [...]
  }
}
```

---

## ⚙️ 설정 및 커스터마이징

### 환경 변수

| 키 | 설명 | 필수 |
|---|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API v3 키 | N |
| `TIKTOK_CONNECTOR_TOKEN` | TikTok 공식/서드파티 커넥터 토큰 | N |
| `INSTAGRAM_CONNECTOR_TOKEN` | Instagram Graph API 토큰 | N |
| `SLACK_WEBHOOK_URL` | Slack 웹훅 URL (알림용) | N |
| `N8N_WEBHOOK_URL` | n8n 웹훅 URL (자동화용) | N |

### API 키 발급 가이드

#### YouTube Data API v3
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 생성
3. "APIs & Services" → "Enable APIs" → "YouTube Data API v3" 활성화
4. "Credentials" → "Create API Key"
5. `.env`에 `YOUTUBE_API_KEY=...` 추가

#### TikTok Research API
1. [TikTok for Developers](https://developers.tiktok.com/) 접속
2. 앱 등록
3. Research API 권한 신청
4. 승인 후 액세스 토큰 발급
5. `.env`에 `TIKTOK_CONNECTOR_TOKEN=...` 추가

### 급상승 임계값 조정

`agents/viral_video_agent/graph.py`에서:

```python
# 기본값: z-score > 2.0
spike_threshold: float = Field(2.0, description="Z-score threshold")

# 더 민감하게 (더 많은 급상승 감지): 1.5
# 덜 민감하게 (확실한 급상승만): 3.0
```

### 시스템 프롬프트 수정

`agents/viral_video_agent/prompts/system.md`를 수정하여:
- 성공 요인 분석 항목 추가/제거
- 플랫폼별 가중치 조정
- 리포트 구조 변경

### 도구 추가/수정

`agents/viral_video_agent/tools.py`에서:
- 새로운 플랫폼 추가 (예: Shorts, Reels)
- 급상승 감지 알고리즘 변경 (이동 평균, ARIMA 등)
- 토픽 클러스터링 개선 (LLM 기반)

---

## 🧪 테스트

### 유닛 테스트

```bash
pytest agents/viral_video_agent/tests/ -v
```

### 빠른 검증 (5~10분)

아래 명령으로 샘플 기반 실행 검증:
```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "K-pop" \
  --market KR \
  --platform youtube
```

---

## 📈 성능 벤치마크

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

**효과:**
- 제품 언급 비디오 자동 탐지
- 급상승 콘텐츠 조기 발견
- 인플루언서 협업 기회 포착

### 시나리오 2: 경쟁사 분석

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "경쟁사명" \
  --market KR,US,JP \
  --window 30d \
  --emit json
```

**효과:**
- 경쟁사 마케팅 전략 파악
- 성공/실패 요인 학습
- 시장별 반응 차이 분석

### 시나리오 3: 크리에이터 발굴

```bash
python scripts/run_agent.py \
  --agent viral_video_agent \
  --query "뷰티 인플루언서" \
  --market KR \
  --platform youtube,instagram \
  --window 7d
```

**효과:**
- 떠오르는 크리에이터 조기 발견
- 협업 ROI 예측 (참여율, 성장률 기반)
- 브랜드 핏 판단 (콘텐츠 스타일, 타겟층)

---

## 🐛 문제 해결

### API 키 없음
- **증상**: `⚠️  No API keys found, using sample data`
- **해결**: 정상입니다! 샘플 데이터로 계속 진행하거나 API 키 설정

### 급상승 감지 안됨
- **증상**: `spike_detected: 0`
- **원인**: 샘플 데이터는 랜덤 값 (실제 스파이크 없을 수 있음)
- **해결**:
  - 임계값 낮추기: `spike_threshold=1.5`
  - 실제 API 사용
  - 다른 query 시도

### NumPy 오류
- **증상**: `ModuleNotFoundError: No module named 'numpy'`
- **해결**: `pip install numpy`

### 플랫폼 API 제한
- **증상**: `429 Too Many Requests`
- **해결**:
  - API 호출 간격 조정 (rate limiting)
  - 유료 플랜 전환
  - 캐싱 활용

---

## 🔄 로드맵

### v1.0 (현재)
- ✅ YouTube, TikTok 기본 지원
- ✅ z-score 기반 급상승 감지
- ✅ 간단한 토픽 클러스터링
- ✅ 성공 요인 체크리스트

### v1.1 (계획)
- [ ] Instagram Reels 지원
- [ ] 실시간 스트리밍 감지
- [ ] 머신러닝 기반 바이럴 예측
- [ ] 경쟁사 벤치마킹 자동화

### v2.0 (장기)
- [ ] 감정 분석 (댓글, 반응)
- [ ] 영상 내용 분석 (썸네일 AI 인식)
- [ ] 자동 알림 (임계값 도달 시)
- [ ] 대시보드 연동 (실시간 차트)

---

## 📚 참고 자료
- [prompts/system.md](prompts/system.md) - 시스템 프롬프트
- [tools.py](tools.py) - 도구 구현
- [graph.py](graph.py) - LangGraph 정의
- [YouTube Data API v3](https://developers.google.com/youtube/v3)
- [TikTok Research API](https://developers.tiktok.com/)
- [z-score 통계](https://en.wikipedia.org/wiki/Standard_score)

---

## 🤝 기여

기여는 언제나 환영합니다!

**우선순위 기여 항목:**
1. 새 플랫폼 지원 (Instagram Reels, YouTube Shorts)
2. 급상승 감지 알고리즘 개선 (ARIMA, Prophet 등)
3. LLM 기반 토픽 클러스터링
4. 썸네일 이미지 분석 (컬러, 구도 AI 인식)

**기여 방법:**
1. Fork the repository
2. Create your feature branch
3. Commit your changes (with tests!)
4. Push to the branch
5. Create a Pull Request

---

## 📝 라이선스

MIT License - 자유롭게 사용하세요!

---

**버전**: 1.0.0
**최종 업데이트**: 2024-10-19
**유지보수자**: Trend Analysis Team
