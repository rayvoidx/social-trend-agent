# 도메인 모델: Mission, Creator, Reward, Insight

> 인사이트에서 마케팅 미션 생성, 크리에이터 매칭까지의 흐름을 정의합니다.

---

## 📊 도메인 개념 정의

### 1. Insight (인사이트)

트렌드 분석 에이전트가 생성하는 핵심 발견 사항입니다. 데이터에 기반한 관찰과 이에 대한 해석을 포함합니다.

**필드 구조:**
```json
{
  "insight_id": "ins_2024112001",
  "type": "trend|sentiment|viral|competitor|opportunity",
  "title": "Z세대에서 '친환경 패키지' 언급 300% 급증",
  "description": "최근 7일간 Z세대(18-24세) 타겟 소셜 미디어에서 '친환경', '제로웨이스트', '리필' 키워드가 전주 대비 300% 증가. 특히 화장품 카테고리에서 언급 집중.",
  "evidence": {
    "source": "social_trend_agent",
    "data_points": [
      {"keyword": "친환경 패키지", "mentions": 1247, "growth": 320},
      {"keyword": "리필 스테이션", "mentions": 856, "growth": 280}
    ],
    "confidence": 0.85
  },
  "sentiment": {
    "positive": 78,
    "neutral": 18,
    "negative": 4
  },
  "actionability": "high",
  "urgency": "medium",
  "created_at": "2024-11-20T09:00:00Z"
}
```

**인사이트 유형:**
- `trend`: 새로운 트렌드 발견
- `sentiment`: 감성 변화 감지
- `viral`: 바이럴 기회 포착
- `competitor`: 경쟁사 동향
- `opportunity`: 마케팅 기회

---

### 2. Mission (미션)

인사이트를 기반으로 생성되는 마케팅 캠페인/액션 단위입니다. 크리에이터에게 의뢰할 콘텐츠 제작 가이드라인을 포함합니다.

**필드 구조:**
```json
{
  "mission_id": "mis_2024112001",
  "insight_id": "ins_2024112001",
  "title": "친환경 패키지 언박싱 캠페인",
  "objective": "Z세대 타겟 친환경 브랜드 이미지 강화",
  "kpi": {
    "primary": {"metric": "engagement_rate", "target": 5.0, "unit": "%"},
    "secondary": [
      {"metric": "views", "target": 100000},
      {"metric": "saves", "target": 5000}
    ]
  },
  "target_audience": {
    "age_range": [18, 24],
    "gender": "all",
    "interests": ["지속가능성", "뷰티", "라이프스타일"],
    "platforms": ["instagram", "tiktok"]
  },
  "content_guide": {
    "format": ["릴스", "숏폼"],
    "duration": "15-30초",
    "tone": "진정성 있는, 캐주얼한",
    "must_include": [
      "친환경 패키지 언박싱 장면",
      "리필/재활용 가능 포인트 설명",
      "#에코뷰티 #친환경패키지 해시태그"
    ],
    "avoid": [
      "과장된 클레임",
      "경쟁사 언급"
    ]
  },
  "budget": {
    "total": 5000000,
    "currency": "KRW",
    "per_creator": 500000
  },
  "timeline": {
    "brief_deadline": "2024-11-22",
    "content_deadline": "2024-11-27",
    "publish_window": ["2024-11-28", "2024-12-05"]
  },
  "status": "draft|recruiting|in_progress|review|completed",
  "created_at": "2024-11-20T10:00:00Z"
}
```

**미션 상태:**
- `draft`: 초안 작성 중
- `recruiting`: 크리에이터 모집 중
- `in_progress`: 콘텐츠 제작 진행 중
- `review`: 검수 단계
- `completed`: 완료

---

### 3. Creator (크리에이터)

콘텐츠를 제작하는 인플루언서/크리에이터 정보입니다. 미션 매칭에 필요한 속성을 포함합니다.

**필드 구조:**
```json
{
  "creator_id": "cre_001",
  "name": "에코뷰티러버",
  "platforms": {
    "instagram": {
      "handle": "@eco_beauty_lover",
      "followers": 52000,
      "engagement_rate": 4.8,
      "avg_views": 15000
    },
    "tiktok": {
      "handle": "@ecobeautylover",
      "followers": 128000,
      "engagement_rate": 6.2,
      "avg_views": 45000
    }
  },
  "categories": ["뷰티", "라이프스타일", "지속가능성"],
  "audience_demographics": {
    "age_range": [18, 28],
    "gender_ratio": {"female": 85, "male": 15},
    "top_regions": ["서울", "경기", "부산"]
  },
  "content_style": {
    "tone": ["진정성", "전문적", "친근함"],
    "formats": ["언박싱", "튜토리얼", "리뷰"],
    "posting_frequency": "주 3-4회"
  },
  "collaboration_history": {
    "total_missions": 12,
    "avg_performance": {
      "engagement_rate": 5.2,
      "on_time_delivery": 100
    },
    "brands": ["브랜드A", "브랜드B", "브랜드C"]
  },
  "pricing": {
    "instagram_reel": 400000,
    "tiktok_video": 350000,
    "bundle_discount": 10
  },
  "availability": {
    "status": "available",
    "next_available": null,
    "blackout_dates": ["2024-12-24", "2024-12-25"]
  },
  "tags": ["에코", "친환경", "비건", "클린뷰티"]
}
```

**크리에이터 매칭 기준:**
1. **카테고리 적합성**: 미션 주제와 전문 분야 일치
2. **오디언스 일치**: 타겟 연령/성별/지역 부합
3. **참여율**: 단순 팔로워 수보다 중요
4. **가격 효율성**: 예산 대비 예상 도달률
5. **협업 이력**: 과거 성과 및 신뢰도

---

### 4. Reward (보상)

미션 완료에 대한 크리에이터 보상 정보입니다.

**필드 구조:**
```json
{
  "reward_id": "rew_2024112001",
  "mission_id": "mis_2024112001",
  "creator_id": "cre_001",
  "type": "fixed|performance|hybrid",
  "base_amount": 400000,
  "performance_bonus": {
    "conditions": [
      {"metric": "views", "threshold": 50000, "bonus": 100000},
      {"metric": "engagement_rate", "threshold": 7.0, "bonus": 150000}
    ]
  },
  "total_earned": 550000,
  "currency": "KRW",
  "payment_status": "pending|processing|completed",
  "payment_date": "2024-12-10"
}
```

**보상 유형:**
- `fixed`: 고정 금액
- `performance`: 성과 기반
- `hybrid`: 기본 + 성과 보너스

---

## 🔄 인사이트 → 미션 → 크리에이터 흐름

```
┌─────────────────┐
│   Insight       │  에이전트가 트렌드 인사이트 생성
│   (발견)        │
└────────┬────────┘
         │
         ▼ 인사이트 기반 미션 설계
┌─────────────────┐
│   Mission       │  목표, KPI, 콘텐츠 가이드 정의
│   (기획)        │
└────────┬────────┘
         │
         ▼ 미션 조건에 맞는 크리에이터 매칭
┌─────────────────┐
│   Creator       │  카테고리, 오디언스, 참여율 기준 선별
│   (매칭)        │
└────────┬────────┘
         │
         ▼ 콘텐츠 제작 및 성과 측정
┌─────────────────┐
│   Reward        │  성과 기반 보상 지급
│   (보상)        │
└─────────────────┘
```

---

## 📝 예시 시나리오

### 시나리오: 화장품 브랜드의 친환경 캠페인

**Step 1: 인사이트 발견**

Social Trend Agent가 다음 인사이트를 발견:
```json
{
  "insight_id": "ins_eco_001",
  "type": "opportunity",
  "title": "Z세대 친환경 패키지 관심 급증",
  "description": "최근 7일간 '#에코뷰티', '#친환경패키지' 해시태그 언급 320% 증가. 특히 언박싱 콘텐츠에서 패키지 재활용성을 언급하는 게시물이 높은 참여율 기록.",
  "actionability": "high",
  "urgency": "high"
}
```

**Step 2: 미션 생성**

브랜드 매니저가 인사이트를 바탕으로 미션 생성:
```json
{
  "mission_id": "mis_eco_001",
  "insight_id": "ins_eco_001",
  "title": "친환경 패키지 언박싱 챌린지",
  "objective": "Z세대 타겟 친환경 브랜드 인식 강화",
  "kpi": {
    "primary": {"metric": "engagement_rate", "target": 5.0}
  },
  "content_guide": {
    "format": ["릴스", "숏폼"],
    "must_include": ["패키지 재활용 방법", "#에코뷰티 해시태그"]
  },
  "budget": {"per_creator": 400000}
}
```

**Step 3: 크리에이터 매칭**

LLM이 미션 조건에 맞는 크리에이터 추천:

```
## 추천 크리에이터 TOP 3

### 1위: @eco_beauty_lover (적합도 95%)

**추천 이유:**
- 카테고리 완벽 일치: 친환경, 클린뷰티 전문
- 높은 참여율: 인스타 4.8%, 틱톡 6.2%
- 타겟 오디언스: Z세대 여성 85%
- 협업 이력: 12회, 평균 성과 우수

**예상 성과:**
- 예상 조회수: 45,000
- 예상 참여율: 5.5%
- ROI: 112원/참여

**협업 제안:**
인스타 릴스 + 틱톡 번들로 의뢰 시 10% 할인 가능
총 비용: 675,000원

---

### 2위: @green_lifestyle_kr (적합도 88%)
...

### 3위: @minimal_beauty (적합도 82%)
...
```

**Step 4: 성과 측정 및 보상**

캠페인 종료 후:
```json
{
  "reward_id": "rew_eco_001",
  "creator_id": "cre_001",
  "base_amount": 400000,
  "performance_bonus": {
    "views_bonus": 100000,
    "engagement_bonus": 150000
  },
  "total_earned": 650000,
  "actual_performance": {
    "views": 68000,
    "engagement_rate": 7.2
  }
}
```

---

## 🤖 LLM 프롬프트 활용

### 인사이트 → 미션 생성 프롬프트

```
다음 인사이트를 바탕으로 마케팅 미션을 설계하세요.

인사이트:
{insight_json}

다음 항목을 포함한 미션을 생성하세요:
1. 미션 제목 (명확하고 행동 지향적)
2. 목표 (구체적인 마케팅 목표)
3. 핵심 KPI (측정 가능한 지표 + 목표값)
4. 타겟 오디언스 (연령, 성별, 관심사, 플랫폼)
5. 콘텐츠 가이드 (포맷, 톤, 필수 포함 사항, 주의 사항)
6. 예산 범위 (크리에이터당 예상 비용)
7. 타임라인 (제작~게시 일정)

JSON 형식으로 출력하세요.
```

### 미션 → 크리에이터 매칭 프롬프트

```
다음 미션에 최적화된 크리에이터를 추천하세요.

미션 정보:
{mission_json}

크리에이터 풀:
{creators_json}

다음 기준으로 TOP 3 크리에이터를 추천하세요:
1. 카테고리 적합성 (미션 주제와 전문 분야)
2. 오디언스 일치도 (타겟 연령/성별/지역)
3. 참여율 (팔로워 대비 실제 참여)
4. 가격 효율성 (예산 대비 예상 ROI)
5. 협업 신뢰도 (과거 성과, 납기 준수율)

각 크리에이터에 대해:
- 적합도 점수 (0-100%)
- 추천 이유 (3가지)
- 예상 성과 (조회수, 참여율)
- 협업 제안 (플랫폼 조합, 할인 가능 여부)
```

---

## 📚 참고 자료

- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - 시스템 전체 개요
- [README.md](../README.md) - 에이전트 사용법
- [automation/n8n/README.md](../automation/n8n/README.md) - 자동화 워크플로우
