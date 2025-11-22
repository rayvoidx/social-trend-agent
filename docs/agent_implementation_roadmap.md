## Agent Implementation Roadmap (Step 3)

### 1. 우선순위 정리 (High / Medium / Low)

- **High (즉시)**  
  - 실제 SNS API 연동 (X/Instagram/TikTok/네이버/YouTube) 보강  
  - 날짜 파싱 및 타임라인 정비 (`_ts` 교체, 시계열 분석 가능 상태로)  
  - 영속 저장소 도입 (Redis + Postgres, 인메모리 저장소 단계적 치환)  
  - 감성·키워드·토픽 분석을 LLM/전용 모델 기반으로 고도화  
  - 기본 RAG 인덱스 구축(Pinecone) 및 키워드 기반 검색 → 임베딩 기반 검색 전환  
  - PII/안전성 필터 1차 확장 (정규식 + 정책 강화, 키 로그 마스킹)

- **Medium (단기)**  
  - Self-Refine 루프 및 구조화 출력(JSON) 적용  
  - Human-in-the-loop 워크플로우 및 대시보드 연동  
  - 모니터링/메트릭/로그 구조화(Prometheus + JSON logging)  
  - FastAPI 레이어 Rate limiting 미들웨어 적용  
  - 테스트 강화 (E2E, LLM 출력 회귀 테스트)

- **Low (중장기)**  
  - 고급 타임시리즈 트렌드 분석 (계절성, 이벤트 영향)  
  - 다국어 확장 및 언어별 파이프라인 튜닝  
  - Creator 매칭/Reward 최적화를 위한 추천 모델 도입

---

### 2. High Priority 상세 구현 단계

#### 2.1 실제 SNS API 연동

1. **X(Twitter) 강화**  
   - 할 일:  
     - 환경 변수 확장: `X_BEARER_TOKEN` 외에 Academic/Enterprise API 키/시크릿 구조를 고려한 설정 키 정의.  
     - `src/agents/social_trend/tools.py`의 `fetch_x_posts`를 **커넥터 모듈**로 분리 (`src/integrations/social/x_client.py` 등)  
     - 최근 검색 외에:  
       - (가능 시) full-archive search / filtered stream 엔드포인트 래핑  
       - 쿼리 빌더(언어, 지역, 리트윗 제외, 미디어 포함 등) 지원  
   - 산출물:  
     - 재사용 가능한 X 클라이언트, 예외/레이트리밋 처리 포함  
     - 테스트: API 키 미설정 시 샘플, 설정 시 실제 응답을 사용하는 통합 테스트.

2. **Instagram 연동**  
   - 할 일:  
     - Meta Graph API 또는 서드파티 커넥터를 위한 설정 구조 정의:  
       - `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`  
       - 대안: `INSTAGRAM_CONNECTOR_URL`, `INSTAGRAM_CONNECTOR_TOKEN` (서드파티)  
     - `fetch_instagram_posts`를 커넥터 호출로 대체하고, 현재 샘플 함수는 폴백 로직으로 유지.  
   - 산출물:  
     - 해시태그/계정 기반 최근 포스트 수집 함수, 페이징/레이틀리밋 핸들링.  
     - 인테그레이션 테스트: 샌드박스 계정 기준 간단 검색 플로우.

3. **TikTok 연동**  
   - 할 일:  
     - 현재 `src/agents/viral_video/tools.py`의 `_fetch_tiktok_stats` 서드파티 연동 구조를 참고해, Social Trend용 텍스트 피드 커넥터(`fetch_tiktok_posts`)를 추가.  
     - 환경 변수: `TIKTOK_CONNECTOR_TOKEN`, `TIKTOK_API_URL` 정리 및 README/문서화.  
   - 산출물:  
     - 시장/키워드/해시태그 기반 TikTok 포스트 수집 함수.  

4. **네이버 블로그/뉴스, YouTube 정리**  
   - 할 일:  
     - 이미 구현된 `fetch_naver_blog_posts`, `search_news`, `_fetch_youtube_stats`를 공통 수집 인터페이스로 노출.  
     - 공통 인터페이스: `fetch_posts(source, query, ...) -> List[CollectedItem]` 형태 정리.  

#### 2.2 날짜 파싱 및 타임라인 정비

1. `_ts()` 개선 (`src/agents/social_trend/tools.py`)  
   - 할 일:  
     - 포맷별 파서 구현: ISO8601, RFC3339, Twitter/Instagram/TikTok/Feedparser 날짜 형식.  
     - 실패 시 None 반환, 로깅으로 추적.  
   - 산출물:  
     - 실제 게시 시간 기반 시계열 분석/정렬 가능 상태.

2. 타임 윈도우 필터링  
   - 할 일:  
     - `time_window`(예: `24h`, `7d`, `30d`)를 datetime 범위로 변환하는 유틸 공통화 (`src/core/datetime_utils.py` 등).  
     - 수집 이후 정제 단계에서 `published_at`이 범위 밖인 데이터는 제외.  

#### 2.3 영속 저장소 (Redis + Postgres)

1. 저장소 인터페이스 정의  
   - 할 일:  
     - `src/domain/models.py`의 `BaseRepository`를 기준으로, `SqlRepository`, `RedisRepository` 인터페이스 설계.  
     - 연결 설정: `DATABASE_URL` (Postgres), `REDIS_URL`.  

2. 인메모리에서 Postgres로 단계적 마이그레이션  
   - 할 일:  
     - `InsightRepository`, `MissionRepository`, `CreatorRepository`, `RewardRepository`에 대해 Postgres 구현 추가.  
     - 초기에는 Dual-write (인메모리 + Postgres)에 쓰고, 읽기는 인메모리 → 점진적으로 Postgres로 전환.  

3. Redis 활용  
   - 할 일:  
     - 최근 수집 결과, 중복 체크 키(해시), Job 상태, 캐시(현재 `@cached` 사용 중)를 Redis 백엔드로 이동.  

#### 2.4 분석 모듈 고도화 (LLM/모델 기반)

1. 감성 분석 개선  
   - 할 일:  
     - News/Social/Viral에서 공통으로 사용할 `analyze_sentiment_llm(texts)` 또는 ML 모델 인터페이스 정의.  
     - 옵션:  
       - 한국어 중심: KoELECTRA, KcBERT 등 사전학습된 감성 모델  
       - 다국어/복합: LLM 함수 호출(JSON 출력)
   - 산출물:  
     - 기존 키워드 기반 감성 결과를 대체 또는 보강하는 구조체 (예: `model: "llm|koelectra"`, `confidence` 포함).

2. 키워드/토픽 클러스터링  
   - 할 일:  
     - TF-IDF + KMeans 또는 BERTopic 기반 토픽 모델링 모듈을 `src/integrations/analysis/topic_modeling.py`로 분리.  
     - LLM 기반 요약과 결합하여 “토픽별 인사이트” 생성.

#### 2.5 기본 RAG 인덱스 구축

1. Pinecone 설정  
   - 할 일:  
     - `.env` 및 설정: `PINECONE_API_KEY`, `PINECONE_ENV`, `PINECONE_INDEX_NAME`.  
     - `src/integrations/retrieval/vectorstore_pinecone.py` 기능 점검 및 Social/News/Viral 에이전트에서 호출하는 래퍼 함수 정의.  

2. 인덱싱 파이프라인  
   - 할 일:  
     - Social/News/Viral 각각에 대해 `build_corpus(normalized) → embed → upsert` 단계 구현.  
     - 쿼리 시 `retrieve_relevant_items`를 Pinecone 기반 검색으로 교체.  

---

### 3. Medium Priority 상세 구현 단계

#### 3.1 Self-Refine + 구조화 출력

1. 구조화 출력(JSON)  
   - 할 일:  
     - 감성/키워드/토픽/인사이트/미션 생성에 대해 JSON 스키마 정의 (도메인 문서와 일치시키기).  
     - LangChain 또는 직접 OpenAI/Anthropic JSON mode를 사용하여 파서 오류를 줄이고, Pydantic 모델(`Insight`, `Mission`)로 바로 매핑.  

2. Self-Refine 루프  
   - 할 일:  
     - 초안 응답 → 평가 프롬프트(모호성/누락/액션가능성/편향) → 수정 지침 → 재생성 루프 구현.  
     - LangGraph에서 노드 2~3개로 구성(초안 생성, 평가, 재작성).

#### 3.2 Human-in-the-loop 및 대시보드 연동

1. 상태 모델 확장  
   - 할 일:  
     - `Insight`, `Mission`에 `status` 필드를 확장: `draft`, `pending_review`, `approved`, `rejected`.  

2. API/프론트 연동  
   - 할 일:  
     - Python `src/api/routes/dashboard.py`와 TypeScript `backend_ts`/`frontend` 대시보드에 검토/승인/수정 API 및 UI 추가.  

#### 3.3 모니터링/로그/Rate limiting

1. 로깅/메트릭  
   - 할 일:  
     - LLM 호출, 외부 API 호출에 대해 공통 로깅 미들웨어 작성 (run_id, latency, 비용 등).  
     - Prometheus exporter와 Grafana 대시보드 템플릿 추가.  

2. Rate limiting  
   - 할 일:  
     - FastAPI 미들웨어로 IP/Key별 요청 제한 추가.  

---

### 4. Low Priority (중장기) 단계

1. 고급 타임시리즈 분석  
   - 할 일:  
     - TimescaleDB 또는 시계열 라이브러리 연동, 시즌성/트렌드/이벤트 영향 분석 모듈 추가.  

2. 다국어 확장  
   - 할 일:  
     - 언어 감지 결과에 따라 언어별 토크나이저/불용어/모델 선택.  

3. Creator/Reward 추천 모델  
   - 할 일:  
     - 과거 미션/성과 데이터를 기반으로 협업 추천 및 보상 최적화 모델 시도.

---

### 5. 실제 구현 순서 제안 (요약)

1. **1주차**: SNS API 커넥터(X/Instagram/TikTok) + `_ts` 개선 + 타임 윈도우 필터  
2. **2주차**: Redis/Postgres 도입 및 인메모리 저장소 단계적 치환  
3. **3주차**: LLM/모델 기반 감성/키워드/토픽 분석 모듈 도입  
4. **4주차**: Pinecone RAG 인덱스 및 검색 경로 전환  
5. **5주차 이후**: Self-Refine, Human-in-the-loop, 모니터링/Rate limiting, 타임시리즈·다국어·추천 모델 순으로 확장


