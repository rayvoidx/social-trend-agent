## Agent Multistage Architecture (Step 2)

### 1. 상위 목표
- **목표 1**: 뉴스/소셜/바이럴 에이전트를 “단일 파이프라인”에서 `수집 → 정제 → 저장 → 임베딩/RAG → LLM 추론 → 검증 → Human Review → 도메인 객체(Insight/Mission) 생성`으로 분리된 멀티스테이지 아키텍처로 전환.
- **목표 2**: 최신 LLM 패턴(함수 호출, 구조화 출력, Self-Refine, 임베딩 RAG, 멀티LLM 백엔드)을 공통 레이어로 추상화해 에이전트 간 재사용.
- **목표 3**: 도메인 계층(`Insight → Mission → Creator → Reward`)과 에이전트 파이프라인을 자연스럽게 연결하여 “트렌드 분석 → 실행 가능한 마케팅 미션”까지 한 번에 이어지는 흐름을 만든다.

---

### 2. 전체 아키텍처 개요

멀티스테이지 파이프라인을 다음 7개 계층으로 정의한다.

1. **Ingestion Layer (수집 계층)**  
   - 책임: X/Instagram/TikTok/Blog/RSS/YouTube 등 외부 소스에서 원본 이벤트를 받아오는 역할.  
   - 구현 위치: `src/agents/*/tools.py`의 fetch 함수들을 `src/integrations/` 하위 커넥터로 점진적 분리.

2. **Cleansing & Normalization Layer (정제·정규화 계층)**  
   - 책임: 타임스탬프 파싱, 언어 감지, 스팸/저품질 필터링, 컨텐츠 중복 제거, 공통 스키마(`CollectedItem`)로 변환.  
   - 구현 위치: 기존 `normalize_items`, `_ts`를 확장하여 `src/agents/shared` 또는 `src/infrastructure` 레벨 공용 유틸로 승격.

3. **Storage & Caching Layer (저장·캐싱 계층)**  
   - 책임:  
     - **단기**: Redis에 최근 수집 결과/잡 상태/중복 체크 키(해시) 저장  
     - **장기**: Postgres에 정규화된 아이템, 인사이트, 미션, 크리에이터, 실행 로그 저장  
   - 구현 위치: `src/domain/models.py`의 `InMemoryRepository`를 인터페이스로 유지하고, `PostgresRepository`, `RedisCache` 구현 추가.

4. **Embedding & Retrieval Layer (임베딩·검색 계층)**  
   - 책임: 텍스트/메타데이터를 임베딩으로 변환하고 Pinecone(또는 호환 벡터 DB)에 저장, 쿼리 시 유사도 기반 검색.  
   - 구현 위치: `src/integrations/retrieval/vectorstore_pinecone.py` 활용, 에이전트별 `build_corpus → embed → upsert → query` 파이프라인 정의.

5. **LLM Reasoning & Tools Layer (LLM 추론·도구 계층)**  
   - 책임:  
     - 함수 호출/구조화 출력 기반 LLM 호출 추상화  
     - 감성 분석, 키워드 추출, 토픽 클러스터링, 인사이트 요약, 미션 생성 등 “도메인 태스크”를 LLM Tool로 정의  
   - 구현 위치: `src/integrations/llm/`에 공통 LLM 클라이언트/툴 인터페이스 정의, 각 에이전트의 `tools.py`는 이를 조합만 하도록 축소.

6. **Safety & Governance Layer (안전성·거버넌스 계층)**  
   - 책임: PII 마스킹, 안전성 분류, 정책 감시, API 키 마스킹, Rate Limiting, 감사 로그.  
   - 구현 위치: `src/core/` 및 `src/infrastructure/monitoring.py`, `retry.py`, `session_manager.py`와 연계.

7. **Orchestration & Human-in-the-loop Layer (오케스트레이션·휴먼 루프 계층)**  
   - 책임: LangGraph + 작업 큐(Celery/Redis)를 이용해 단계별 워크플로우를 정의하고, 중간 결과를 프론트엔드/대시보드에서 검토·승인 가능하게 제공.  
   - 구현 위치:  
     - 그래프 정의: `src/agents/*/graph.py`  
     - 워커: `src/infrastructure/distributed.py` (기존 패턴 재사용)  
     - API: `src/api/routes/dashboard.py`, `backend_ts` API와의 연동.

---

### 3. 에이전트 별 멀티스테이지 플로우 정의

#### 3.1 Social Trend Agent 멀티스테이지 플로우

1. **Stage S1 – 수집(Ingestion)**  
   - 입력: `query`, `sources`, `time_window`  
   - 작업:  
     - `fetch_x_posts`, `fetch_instagram_posts`, `fetch_naver_blog_posts`, `fetch_rss_feeds`를 **커넥터 레이어**로 분리  
     - Instagram/TikTok은 실제 API/서드파티 엔드포인트를 위한 설정 슬롯(Env + Config) 추가  
   - 출력: 원본 `CollectedItem` 리스트 (source별)

2. **Stage S2 – 정제/정규화(Cleansing & Normalization)**  
   - 작업:  
     - `_ts()`를 실제 날짜 파싱 함수로 교체 (ISO/RFC3339, Twitter/Instagram/TikTok 포맷 지원)  
     - URL/콘텐츠 해시 기반 중복 제거 (`sha256(url or content)`), 언어 감지(`langdetect` or fastText), 간단 스팸 필터(블랙리스트/짧은 텍스트 제거).  
   - 출력: **플랫폼 중립 스키마**의 `normalized` 리스트:  
     - `source, title, url, content, published_at, language, author, engagement(views/likes/comments)` 등.

3. **Stage S3 – 저장(Storage)**  
   - 작업:  
     - Redis: 최근 `normalized`를 TTL 기반으로 저장 (RAG 인덱싱 전 버퍼).  
     - Postgres: 시간창에 맞는 수집 로그/아이템 스냅샷을 테이블에 Append-Only로 기록.  
   - 출력: `item_ids` 리스트 및 조회 가능한 조회키(run_id, query, time_window).

4. **Stage S4 – 임베딩 & RAG 인덱싱(Embedding & Indexing)**  
   - 작업:  
     - `title + content`를 대상으로 임베딩 생성(OpenAI Embeddings, Voyage, bge-m3 등 설정 가능).  
     - Pinecone 인덱스에 upsert (`namespace = social_trend/{query}/{time_window}` 패턴).  
   - 출력: 인덱스 키 리스트, RAG-ready 상태.

5. **Stage S5 – 1차 LLM 분석(Structured LLM Analysis)**  
   - 작업:  
     - 함수 호출/JSON 스키마를 이용해 **감성/키워드/토픽/클러스터**를 한 번에 도출하는 LLM 호출:  
       - 입력: 상위 N개 대표 문서(시간/참여도 기반 샘플링) + 질의 + 시간창  
       - 출력: `{ sentiment, keywords, topics, clusters, anomalies }` 구조체  
   - 구현: `src/integrations/llm/analysis_tools.py` (예: `analyze_social_trend_structured(...)`).

6. **Stage S6 – Self-Refine + RAG 기반 인사이트 생성**  
   - 작업:  
     - RAG 검색: 질의/토픽 별로 Pinecone에서 관련 문서 K개 검색.  
     - LLM에 “초안 인사이트”를 생성시키고, 별도의 **평가 프롬프트**로 스스로 품질/명확성/액션가능성을 평가(Self-Refine).  
     - 필요시 2~3회 루프를 돌며 수정본 생성.  
   - 출력: 고품질 인사이트 텍스트 + 구조화된 요약 (핵심 포인트, 액션 아이템 리스트).

7. **Stage S7 – Safety/PII 필터링 & Human Review 큐 등록**  
   - 작업:  
     - PII/안전성 필터(정규식 + LLM 기반 분류기)를 통과시켜 마스킹/삭제.  
     - `Insight` 도메인 객체 빌드 후 `INSIGHT_REPOSITORY` (향후 Postgres) 저장.  
     - 상태: `draft` 인사이트를 “검토 대기 큐”에 올리고, 대시보드/Slack 등으로 알림.  
   - 출력: Human-in-the-loop를 거칠 수 있는 인사이트 엔티티.

8. **Stage S8 – Insight → Mission 파이프라인 연계 (선택적 자동화)**  
   - 작업:  
     - 선택된 인사이트에 대해 LLM을 사용해 `Mission` 초안을 생성 (목표/KPI/타겟/콘텐츠 가이드/예산 크게 5블록).  
     - `docs/domain/domain_mission_creator.md`에 정의된 스키마를 그대로 따르는 JSON 구조 출력.  
   - 출력: `Mission` 도메인 객체(`status = draft`) 생성 및 저장.

#### 3.2 News Trend Agent 멀티스테이지 플로우 (요약)
- News 에이전트는 이미 `search_news → analyze_sentiment → extract_keywords → summarize_trend` 구조를 갖고 있으므로 아래를 추가한다.
1. 수집 후 정제 단계에 **중복 제거/시계열 정렬/언어 감지** 추가.  
2. 정규화된 뉴스 본문/제목에 대해 **임베딩 생성 + Pinecone 인덱싱** 수행.  
3. `retrieve_relevant_items`를 키워드 방식에서 RAG 호출로 교체 (`query_embedding` 기반 top-k).  
4. 요약 단계에서: `초안 요약 → LLM 기반 품질 평가 → 필요시 재요약(Self-Refine)` 체인으로 변경.  
5. 최종 결과를 `Insight`로 저장 후, 도메인 파이프라인(미션 생성)과 연결.

#### 3.3 Viral Video Agent 멀티스테이지 플로우 (요약)
1. 수집: YouTube/TikTok API에서 시청/참여 지표 + 메타데이터 수집.  
2. 정제: 국가/언어/카테고리별 필터링, 스팸/중복 영상 제거.  
3. Spike 검출: 기존 Z-score 로직을 유지하되, 시계열 창/플랫폼별로 세분화.  
4. 임베딩: 영상 제목+설명+태그 기반 텍스트 임베딩, Pinecone 저장.  
5. LLM 분석: “바이럴 성공 요인”, “크리에이티브 패턴”, “플랫폼별 전략”을 구조화 출력.  
6. Insight/Mission 연계: 특정 카테고리(예: TikTok 뷰티 숏폼)에서 유망한 포맷에 대해 미션 템플릿 생성.

---

### 4. LLM Reasoning 계층 설계 (최신 트렌드 반영)

1. **멀티LLM 백엔드 추상화**  
   - `LLM_PROVIDER`에 따라 OpenAI/Anthropic/Gemini/Ollama 선택 (이미 부분 구현됨).  
   - 공통 인터페이스: `chat(messages, tools=None, response_format=None)` 형태로 래핑.  
   - 역할 분리:  
     - 고품질 분석/요약: GPT-5.1
     - 임베딩: 전용 임베딩 모델(OpenAI text-embedding-3-large 등)  
     - 안전성: Llama Guard 계열 또는 전용 moderation API.

2. **함수 호출 / 구조화 출력**  
   - 감성, 키워드, 토픽, 인사이트, 미션, 크리에이터 추천 등은 **JSON 스키마를 정의**하고 LLM에게 이를 채우도록 요구.  
   - LangChain/JSON mode를 이용해 파싱 실패를 줄이고, 도메인 객체로 바로 변환 가능하게 설계.

3. **Self-Refine / Self-Check 루프**  
   - 초안 응답을 생성한 뒤, 별도 평가 프롬프트로 “모호성, 누락, 액션가능성, 편향”을 체크.  
   - 평가 결과에 따라 “수정 지침”을 생성하고, 이를 다시 LLM에게 전달해 개선본 생성.  
   - 이 루프를 1~2회로 제한해 Latency와 품질을 트레이드오프.

4. **Tool-augmented Reasoning**  
   - LLM이 필요 시 다음 툴을 호출할 수 있도록 정의:  
     - `search_recent_news`, `query_rag_index`, `fetch_realtime_metrics`, `generate_mission_draft`, `rank_creators_by_fit` 등.  
   - LangGraph에서 노드로 등록하고, 도메인 상태(`Insight`, `Mission`)를 그래프 스테이트로 관리.

---

### 5. Safety & Governance 설계

1. **PII 확장**  
   - 정규식 + LLM 조합으로 이름, 주소, 주민번호, 카드번호, 계좌번호 등 탐지.  
   - `redact_pii`를 확장해 마스킹 레벨(완전 제거/부분 마스킹)을 정책으로 제어.

2. **안전성 분류기**  
   - 키워드 기반 `check_safety`에서 벗어나 LLM 기반 분류(예: “허용/주의/차단”)를 추가.  
   - 위험 카테고리(증오, 폭력, 자해, 성인, 정치 등)를 태깅하고, 정책에 따라 후속 조치(차단/리뷰 요구).

3. **API 키/시크릿 관리**  
   - `main.py`에서 키 일부를 노출하지 않고, “configured” 여부만 로그.  
   - 환경 변수 → Secrets Manager(Vault, AWS Secrets Manager 등)로 전환 가능하도록 추상화.

4. **Rate Limiting & 감사 로그**  
   - FastAPI 레이어에서 IP/Key 기반 Rate Limit 미들웨어 추가.  
   - 모든 LLM/외부 API 호출에 대해 `run_id`, `user_id`, `timestamp`, `latency`, `status`, `cost` 메타데이터를 구조화 로그로 기록.

---

### 6. Orchestration & Human-in-the-loop

1. **LangGraph 기반 그래프 정의**  
   - 각 에이전트별로 위 Stage들을 LangGraph 노드로 모델링 (`S1_ingest`, `S2_clean`, ..., `S8_mission` 등).  
   - 조건 분기: 에러/품질 부족/안전성 문제 발생 시 “재시도/완화/휴먼 검토” 경로로 분기.

2. **작업 큐/스케줄러 연계**  
   - 긴 작업(대량 수집, 대규모 RAG 인덱싱)은 Celery/Redis Queue로 비동기 처리.  
   - `workflows/n8n`과도 연계해 매일/매주 리포트 자동 실행.

3. **Human Review UI 연동**  
   - `Insight`/`Mission` 상태에 `draft/pending_review/approved/rejected` 추가.  
   - 프론트엔드 대시보드에서 초안 내용/근거 데이터/추천 액션을 보여주고, 사용자가 수정·승인하면 최종 상태로 업데이트.

---

### 7. 이 설계가 해결하는 핵심 문제 요약

- **데이터 수집/정제**: 실제 API 연동, 중복 제거, 날짜 파싱, 스팸 필터로 “신뢰할 수 있는 원천 데이터” 확보.  
- **분석 품질**: 키워드 기반 분석에서 벗어나 구조화된 LLM 분석 + 임베딩 기반 RAG + Self-Refine로 품질 향상.  
- **에이전트 역할 명확화**: “트렌드 분석 → 인사이트 → 미션 생성 → 크리에이터 매칭” 까지 도메인 플로우와 일치하는 멀티스테이지 설계.  
- **프로덕션 준비도**: 영속 저장소, 안전성/PII, 오케스트레이션, Human-in-the-loop 도입으로 실제 운영 가능한 에이전트 시스템에 한 단계 근접.


