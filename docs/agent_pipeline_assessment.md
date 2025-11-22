# Agent Pipeline Assessment (Step 1)

## 목적 및 범위
- 2025-11-21 기준 v0.1 파이프라인이 최신 LLM 에이전트 트렌드(멀티스텝 추론, 자기검증, 임베딩 기반 RAG, 인적 검증 루프 등)와 비교해 어떤 한계를 가지는지 진단
- 진단 결과는 2단계 설계 고도화 작업의 입력 자료로 사용

## 현재 파이프라인 스냅샷
- CLI 또는 FastAPI 진입점에서 바로 LangGraph `run_agent` 함수를 호출하며, 각 에이전트는 `수집 → 정규화 → 휴리스틱 분석 → 단일 LLM 요약 → 리포트` 순으로 직렬 실행됨
- 오케스트레이션/상태 관리가 별도 계층으로 나뉘어 있지 않아 재시도, 병렬 분기, 휴먼 리뷰 삽입이 어렵고, LangGraph의 이벤트 루프나 Self-Reflective 패턴도 사용하지 않음

```111:166:src/agents/social_trend/graph.py
def run_agent(
    query: str,
    sources: Optional[List[str]] = None,
    ...
    normalized = normalize_items(all_items)
    texts = [it.get("title", "") + "\n" + it.get("content", "") for it in normalized]
    analysis = analyze_sentiment_and_keywords(texts)
    llm_insights = _generate_llm_insights(...)
    ...
    return {
        "query": query,
        "time_window": time_window,
        ...
    }
```

## 단계별 한계 진단

### 1. 데이터 수집 계층
- **Instagram/TikTok 채널은 전부 샘플 데이터**: 실제 Graph API/TikTok Business API 요청이 존재하지 않아 시장 신호를 반영하지 못함.
- **X(Twitter)도 최근 검색 1개 엔드포인트에 의존**: Bearer token 기반 단일 호출만 제공되어 장기 아카이브, 실시간 스트림, 고급 필터가 불가.

```68:105:src/agents/social_trend/tools.py
def fetch_instagram_posts(...):
    ...
    return _sample_items("instagram", query, max_results)
```

```96:152:src/agents/viral_video/tools.py
def _fetch_tiktok_stats(...):
    """
    Fetch TikTok trending videos
    ...
    """
    ...
    return _get_sample_tiktok_data(market)
```

- **타임라인 정보 부재**: `_ts()`가 입력 값과 무관하게 `time.time()`을 반환하여 시간순 분석, 중복 제거, 윈도우링이 불가능.

```240:245:src/agents/social_trend/tools.py
def _ts(v: Optional[str]) -> Optional[float]:
    try:
        return time.time()
    except Exception:
        return None
```

### 2. 정규화 및 품질 관리
- `normalize_items`는 키 복사 외 로직이 없어 언어/플랫폼별 스키마 차이를 보정하지 못하고, URL 기반 중복 제거도 없다.
- 스팸 탐지, 언어 감지, 멀티모달 메타데이터(이미지, 썸네일) 정제 기능이 부재해 LLM 입력 품질이 낮다.

### 3. 분석 모듈
- 감성/키워드 분석이 단순 키워드 카운팅 수준이라 다국어, 역설/풍자, 도메인 맥락을 구분하지 못한다.

```175:222:src/agents/social_trend/tools.py
def analyze_sentiment_and_keywords(texts: List[str]) -> Dict[str, Any]:
    positive_tokens = ["great", "good", "love", "추천", "만족", "좋"]
    negative_tokens = ["bad", "hate", "불만", "나쁨", "싫", "문제"]
    ...
    top_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
```

- News/Viral 에이전트 역시 단일 LLM 요약 전 단계에서 구조화된 특징 추출이나 임베딩 생성을 하지 않기 때문에, 멀티모달 혹은 장문 데이터를 다룰 때 정보 손실이 발생한다.

### 4. LLM 사용 패턴
- `_generate_llm_insights`는 단일 프롬프트 호출만 수행하며, Reason+Act, Self-Ask, tool calling, function calling 등 최신 멀티스텝 패턴을 활용하지 않는다.
- LangGraph 기능을 쓰고 있지만 상태 메모리나 컨디셔널 경로 없이 직렬 체인으로만 사용되어, 자기 검증·재서머라이즈 루프 구현이 어렵다.

### 5. Retrieval & Memory
- `retrieve_relevant_items`는 키워드 오버랩 스코어만으로 상위 항목을 선정하며, Pinecone 등 벡터 DB가 프로젝트에 포함돼 있음에도 실제 임베딩 생성/저장이 없다.

```469:478:src/agents/news_trend/tools.py
def retrieve_relevant_items(query: str, items: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
    tokens = [t for t in _tokenize(query) if len(t) > 1]
    ...
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[: max(1, top_k)]]
```

- 장기 메모리는 `src/domain/models.py`의 전역 인메모리 저장소에만 기록되므로 서버 재시작 시 모든 인사이트/미션/리워드 정보가 손실된다.

```316:339:src/domain/models.py
class InMemoryRepository(Generic[TModel], BaseRepository[TModel]):
    ...
    def __init__(self) -> None:
        self._store: Dict[str, TModel] = {}
    def create(self, obj: TModel) -> TModel:
        ...
        self._store[str(obj_id)] = obj
        return obj
```

### 6. 안전성 & 거버넌스
- PII 마스킹과 세이프티 체크가 이메일/전화 및 5개 키워드만 커버해 실제 규제(예: 주민번호, 카드번호, 민감 토픽)에 대응하지 못한다.

```490:504:src/agents/news_trend/tools.py
def redact_pii(text: str) -> Dict[str, Any]:
    ...
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    ...
def check_safety(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    cats = [kw for kw in _UNSAFE_KEYWORDS if kw in lowered]
```

- `main.py`는 API 키 앞/뒤 일부를 로그로 출력하므로(마스킹 불완전), 운영 환경에서 키 유출 위험이 있다.

```69:72:main.py
model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
logger.info(f"✅ OpenAI configured: {model_name}")
logger.info(f"🔑 API Key: {openai_key[:10]}...{openai_key[-4:]}")
```

### 7. 오케스트레이션 & 관측성
- run_id 기반 로깅/리포트 저장은 있지만, 작업 큐/재시도/부분 실패 복구가 각 모듈에 분산돼 있어 대규모 배치나 멀티테넌트 실행 시 병목이 예상된다.
- 메트릭 역시 `metrics = {"coverage": ..., "factuality": 0.7, "actionability": 0.6}`와 같은 하드코딩 값이라 SLA 모니터링이 불가능하다.

## 최신 LLM 에이전트 트렌드 대비 갭
- **멀티스테이지 Reasoning**: ReAct, Graph-of-Thought, Self-Refine, tool calling, 함수 기반 JSON 출력 등 최신 패턴이 미적용.
- **임베딩/메모리 계층**: 벡터 DB, 장단기 메모리, 사용자 컨텍스트 보존이 없어, 질의 연속성이나 맞춤형 설명 제공이 어렵다.
- **휴먼 루프 & 검증**: 결과 검토/승인 워크플로우, 자동 사실 검증/평가 루프가 없어 품질 보장이 되지 않는다.
- **시계열 인식**: 타임스탬프, 계절성, 이벤트 영향 등을 반영하지 못해 “트렌드” 분석의 핵심 가치가 희석된다.
- **보안/규정 준수**: 키 마스킹, 세분화된 PII 필터, 정책 기반 안전 필터(예: Llama Guard, NeMo Guardrails)가 필요하다.

## Step 2(설계 고도화)를 위한 입력 포인트
- **데이터 계층**: 실제 SNS API, 중복 제거, 타임스탬프/언어 정규화, Redis/Postgres를 포함하는 영속 파이프라인 설계
- **Reasoning 계층**: 임베딩 기반 RAG, Self-Reflective 루프, 함수 호출 기반 구조화 출력, 멀티LLM 백엔드 전략
- **검증/거버넌스**: 휴먼 인 더 루프, 자동 fact-check, 강화된 PII/세이프티 필터, 키 관리 개선
- **관측성/자동화**: 메트릭 표준화(Prometheus), 알람, 작업 큐/스케줄러(Celery/Temporal)로 확장 준비

위 진단 결과를 토대로 2단계에서 “차세대 멀티스테이지 아키텍처 설계”를 정의할 때, 각 한계 항목을 해결하는 구체 설계 포인트로 연결하면 된다.

