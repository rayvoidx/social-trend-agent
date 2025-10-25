# News Trend Agent

> 글로벌 및 국내 뉴스를 수집·분석하여 마케팅·상품기획의 빠른 의사결정을 돕는 트렌드 분석 에이전트

---

## 📌 개요

News Trend Agent는 다양한 뉴스 소스(News API, Naver News, Tavily 등)에서 키워드 기반으로 뉴스를 수집하고, 감성 분석, 키워드 추출, 트렌드 요약을 통해 실행 가능한 인사이트를 제공합니다.

### 주요 기능
- ✅ **자동 데이터 수집**: News API, Naver Open API 연동
- ✅ **감성 분석**: 긍정/중립/부정 비율 분석
- ✅ **키워드 추출**: 빈도 기반 Top-N 키워드
- ✅ **트렌드 요약**: LLM 기반 인사이트 생성
- ✅ **마크다운 리포트**: 출처 링크 포함 완전한 문서
- ✅ **알림 연동**: n8n, Slack 웹훅 지원

---

## 🚀 빠른 시작

### 기본 실행 (샘플 데이터)

```bash
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "전기차" \
  --window 7d
```

### API 키 사용 (실제 데이터)

```bash
# .env 파일 설정
NEWS_API_KEY=your_key
NAVER_CLIENT_ID=your_id
NAVER_CLIENT_SECRET=your_secret

# 실행
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "electric vehicles" \
  --language en \
  --window 24h
```

---

## 🛠️ 아키텍처

### LangGraph 워크플로우

```
┌─────────┐
│ collect │ ─── 뉴스 수집 (News API, Naver, Tavily)
└────┬────┘
     │
┌────▼──────┐
│ normalize │ ─── 데이터 정규화 (title, description, url 등)
└────┬──────┘
     │
┌────▼────┐
│ analyze │ ─── 감성 분석 + 키워드 추출
└────┬────┘
     │
┌────▼──────┐
│ summarize │ ─── LLM 기반 트렌드 요약
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
class NewsAgentState(AgentState):
    query: str                    # 검색어
    time_window: str              # 기간 (24h, 7d, 30d)
    language: str                 # 언어 (ko, en)
    max_results: int              # 최대 결과 수

    raw_items: List[Dict]         # 원본 뉴스
    normalized: List[Dict]        # 정규화된 데이터
    analysis: Dict                # 분석 결과
    report_md: str                # 최종 리포트
    metrics: Dict                 # 품질 메트릭스
    run_id: str                   # 실행 ID
```

---

## 🔧 주요 도구 (Tools)

### 1. search_news
뉴스 검색 및 수집

**시그니처:**
```python
def search_news(
    query: str,
    time_window: str = "7d",
    language: str = "ko",
    max_results: int = 20
) -> List[Dict[str, Any]]
```

**동작:**
- News API (영문 뉴스)
- Naver News API (한글 뉴스)
- API 키 없으면 샘플 데이터로 자동 전환

**출력 예시:**
```json
[
  {
    "title": "전기차 시장 성장세 지속",
    "description": "...",
    "url": "https://...",
    "source": {"name": "Naver News"},
    "publishedAt": "2024-10-17T10:30:00Z",
    "content": "..."
  }
]
```

---

### 2. analyze_sentiment
감성 분석

**시그니처:**
```python
def analyze_sentiment(items: List[Dict[str, Any]]) -> Dict[str, Any]
```

**방법:**
- 키워드 기반 (프로덕션: LLM 사용 권장)
- 긍정 키워드: 성공, 성장, 증가, 호평 등
- 부정 키워드: 실패, 감소, 하락, 비판 등

**출력 예시:**
```json
{
  "positive": 12,
  "neutral": 5,
  "negative": 1,
  "positive_pct": 66.7,
  "neutral_pct": 27.8,
  "negative_pct": 5.6
}
```

---

### 3. extract_keywords
키워드 추출

**시그니처:**
```python
def extract_keywords(items: List[Dict[str, Any]]) -> Dict[str, Any]
```

**방법:**
- 단순 빈도 (프로덕션: TF-IDF 또는 LLM 권장)
- 불용어 제거
- Top 20 키워드 추출

**출력 예시:**
```json
{
  "top_keywords": [
    {"keyword": "전기차", "count": 45},
    {"keyword": "배터리", "count": 23},
    ...
  ],
  "total_unique_keywords": 135
}
```

---

### 4. summarize_trend
트렌드 요약 (LLM)

**시그니처:**
```python
def summarize_trend(
    query: str,
    normalized_items: List[Dict[str, Any]],
    analysis: Dict[str, Any]
) -> str
```

**동작:**
- LLM 호출 (Azure OpenAI, OpenAI, Anthropic, Google, Ollama 지원)
- 현재는 규칙 기반 요약 (TODO: LLM 통합)

**출력 예시:**
```
'전기차'에 대한 전반적인 반응은 **긍정적**입니다.
주요 키워드: 전기차, 배터리, 충전

**실행 권고안:**
- 긍정 반응이 높은 콘텐츠를 중심으로 마케팅 전략 수립
- 주요 키워드를 활용한 SEO 최적화
...
```

---

## 📊 출력 형식

### 마크다운 리포트 구조

```markdown
# 뉴스 트렌드 분석 리포트

**검색어**: [query]
**기간**: [time_window]
**언어**: [language]
**분석 항목 수**: [count]

---

## 📊 감성 분석
- 긍정: X개 (XX%)
- 중립: X개 (XX%)
- 부정: X개 (XX%)

---

## 🔑 핵심 키워드 (Top 10)
1. **키워드1** (XX회)
2. **키워드2** (XX회)
...

---

## 💡 주요 인사이트
[LLM 생성 요약]

---

## 📰 주요 뉴스 (Top 5)
### 1. [제목]
**출처**: [링크]
**발행일**: [날짜]
[요약]

---

⚠️ **주의**: 본 리포트는 AI가 생성한 분석으로, 사실 확인이 필요합니다.
**Run ID**: `[run_id]`
```

### 메트릭스 파일 (JSON)

```json
{
  "run_id": "uuid",
  "timestamp": "20241019_143000",
  "metrics": {
    "coverage": 0.9,       // 수집율
    "factuality": 1.0,     // 출처 신뢰도
    "actionability": 1.0   // 실행 가능 인사이트 포함
  },
  "item_count": 18
}
```

---

## ⚙️ 설정 및 커스터마이징

### 환경 변수

| 키 | 설명 | 필수 |
|---|---|---|
| `NEWS_API_KEY` | NewsAPI.org API 키 (영문 뉴스) | N |
| `NAVER_CLIENT_ID` | Naver Open API 클라이언트 ID | N |
| `NAVER_CLIENT_SECRET` | Naver Open API 시크릿 | N |
| `SLACK_WEBHOOK_URL` | Slack 웹훅 URL (알림용) | N |
| `N8N_WEBHOOK_URL` | n8n 웹훅 URL (자동화용) | N |

### 시스템 프롬프트 수정

`agents/news_trend_agent/prompts/system.md`를 수정하여:
- 증거 우선 원칙 강화/완화
- 감성 분석 키워드 추가
- 리포트 구조 변경

### 도구 추가/수정

`agents/news_trend_agent/tools.py`에서:
- 새로운 뉴스 소스 추가 (예: Tavily, Google News)
- 감성 분석 방법 변경 (LLM 기반으로 업그레이드)
- 키워드 추출 알고리즘 개선 (TF-IDF, LLM)

---

## 🧪 테스트

### 유닛 테스트

```bash
pytest agents/news_trend_agent/tests/ -v
```

### 빠른 검증 (5~10분)

아래 명령으로 샘플 기반 실행 검증:
```bash
python scripts/run_agent.py \
  --agent news_trend_agent \
  --query "전기차" \
  --window 7d
```

---

## 📈 성능 벤치마크

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

## 🐛 문제 해결

### API 키 없음
- **증상**: `⚠️  No API keys found, using sample data`
- **해결**: 정상입니다! 샘플 데이터로 계속 진행하거나 API �� 설정

### 언어 감지 실패
- **증상**: 한글 뉴스에서 영어 키워드 추출
- **해결**: `--language ko` 명시 또는 `tools.py`의 불용어 리스트 확장

### 감성 분석 정확도 낮음
- **증상**: 명백한 긍정 뉴스가 중립으로 분류
- **해결**: LLM 기반 감성 분석으로 업그레이드 (TODO in code)

---

## 🔄 로드맵

### v1.0 (현재)
- ✅ 기본 뉴스 수집 (News API, Naver)
- ✅ 키워드 기반 감성 분석
- ✅ 빈도 기반 키워드 추출
- ✅ 규칙 기반 트렌드 요약

### v1.1 (계획)
- [ ] LLM 기반 감성 분석
- [ ] TF-IDF 키워드 추출
- [ ] LLM 트렌드 요약
- [ ] Tavily 통합

### v2.0 (장기)
- [ ] Vector DB 기반 유사 뉴스 클러스터링
- [ ] 시계열 분석 (트렌드 변화 추적)
- [ ] 자동 알림 (임계값 기반)
- [ ] 대시보드 연동 (Grafana, Metabase)

---

## 📚 참고 자료
- [prompts/system.md](prompts/system.md) - 시스템 프롬프트
- [tools.py](tools.py) - 도구 구현
- [graph.py](graph.py) - LangGraph 정의
- [News API 문서](https://newsapi.org/docs)
- [Naver Open API](https://developers.naver.com/docs/search/news/)

---

## 🤝 기여

기여는 언제나 환영합니다!

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

---

## 📝 라이선스

MIT License - 자유롭게 사용하세요!

---

**버전**: 1.0.0
**최종 업데이트**: 2024-10-19
**유지보수자**: Trend Analysis Team
