# 인사이트 → 미션/크리에이터 프롬프트 설계

> 트렌드 인사이트를 마케팅 미션으로 전환하고, 최적의 크리에이터를 매칭하는 프롬프트 템플릿

---

## 1. 인사이트 → 미션 생성 프롬프트

### INSIGHT_TO_MISSION_PROMPT

```python
INSIGHT_TO_MISSION_PROMPT = """당신은 브랜드 마케팅 전략가입니다. 트렌드 인사이트를 바탕으로 실행 가능한 마케팅 미션을 설계합니다.

## 인사이트 정보

{insight_json}

## 미션 설계 요구사항

다음 항목을 모두 포함한 마케팅 미션을 생성하세요:

### 1. 기본 정보
- **미션 제목**: 명확하고 행동 지향적 (예: "친환경 패키지 언박싱 챌린지")
- **미션 목표**: 구체적인 마케팅 목표 (예: "Z세대 친환경 브랜드 인식 강화")

### 2. 핵심 KPI (측정 가능해야 함)
- **주요 KPI**: 1개 (예: engagement_rate 5.0%)
- **보조 KPI**: 2-3개 (예: views 100,000, saves 5,000)

### 3. 타겟 오디언스
- **연령대**: 구체적 범위 (예: 18-24세)
- **성별**: all/female/male
- **관심사**: 3-5개 키워드
- **플랫폼**: instagram/tiktok/youtube 중 선택

### 4. 콘텐츠 가이드
- **포맷**: 릴스/숏폼/스토리/피드/유튜브 중 선택
- **길이**: 구체적 시간 (예: 15-30초)
- **톤앤매너**: 2-3개 형용사 (예: 진정성 있는, 캐주얼한)
- **필수 포함 사항**: 3-5개 항목
- **주의 사항**: 2-3개 항목

### 5. 예산
- **크리에이터당 예산**: 원화 기준
- **총 예산**: 전체 캠페인 예산

### 6. 타임라인
- **브리프 전달**: D-day 기준
- **콘텐츠 제출**: D+X
- **게시 기간**: 시작일~종료일

## 출력 형식

다음 JSON 형식으로 출력하세요:

```json
{{
  "mission_id": "mis_YYYYMMDD##",
  "insight_id": "{insight_id}",
  "title": "미션 제목",
  "objective": "마케팅 목표",
  "kpi": {{
    "primary": {{"metric": "지표명", "target": 수치, "unit": "단위"}},
    "secondary": [
      {{"metric": "지표명", "target": 수치}},
      ...
    ]
  }},
  "target_audience": {{
    "age_range": [시작, 끝],
    "gender": "all|female|male",
    "interests": ["관심사1", "관심사2", ...],
    "platforms": ["플랫폼1", "플랫폼2"]
  }},
  "content_guide": {{
    "format": ["포맷1", "포맷2"],
    "duration": "길이",
    "tone": "톤앤매너",
    "must_include": ["필수1", "필수2", ...],
    "avoid": ["주의1", "주의2", ...]
  }},
  "budget": {{
    "total": 총액,
    "currency": "KRW",
    "per_creator": 크리에이터당
  }},
  "timeline": {{
    "brief_deadline": "YYYY-MM-DD",
    "content_deadline": "YYYY-MM-DD",
    "publish_window": ["시작일", "종료일"]
  }},
  "status": "draft"
}}
```

## 설계 원칙

1. **인사이트 연결**: 미션이 인사이트의 기회를 직접 활용해야 함
2. **측정 가능**: 모든 KPI는 구체적 수치로 설정
3. **실행 가능**: 크리에이터가 바로 이해하고 제작 가능한 가이드
4. **현실적 예산**: 시장 단가 기준 합리적 범위
5. **적절한 타임라인**: 충분한 제작 시간 + 트렌드 시의성

## 예시

인사이트:
- "Z세대 친환경 패키지 관심 320% 급증"

미션:
- 제목: "친환경 패키지 언박싱 챌린지"
- 목표: "Z세대 친환경 브랜드 인식 강화"
- KPI: engagement_rate 5.0%, views 100,000
- 포맷: 인스타 릴스 15-30초
- 필수: 패키지 언박싱, 재활용 설명, #에코뷰티 태그
"""
```

---

## 2. 미션 → 크리에이터 매칭 프롬프트

### MISSION_TO_CREATOR_PROMPT

```python
MISSION_TO_CREATOR_PROMPT = """당신은 인플루언서 마케팅 전문가입니다. 미션에 최적화된 크리에이터를 추천하고, 협업 전략을 제안합니다.

## 미션 정보

{mission_json}

## 크리에이터 풀

{creators_json}

## 매칭 기준 (가중치)

1. **카테고리 적합성 (25%)**: 미션 주제와 크리에이터 전문 분야 일치도
2. **오디언스 일치도 (25%)**: 타겟 연령/성별/지역 부합 정도
3. **참여율 (20%)**: 팔로워 대비 실제 참여 (좋아요, 댓글, 저장)
4. **가격 효율성 (15%)**: 예산 대비 예상 ROI
5. **협업 신뢰도 (15%)**: 과거 성과, 납기 준수율, 브랜드 리스크

## 출력 형식

다음 형식으로 TOP 3 크리에이터를 추천하세요:

```markdown
## 크리에이터 추천 리포트

### 종합 추천

| 순위 | 크리에이터 | 적합도 | 예상 참여율 | 비용 | ROI |
|------|-----------|--------|------------|------|-----|
| 1 | @handle | 95% | 5.5% | 400K | 112원 |
| 2 | @handle | 88% | 4.8% | 350K | 98원 |
| 3 | @handle | 82% | 5.2% | 300K | 125원 |

---

### 1위: @{handle} (적합도 {score}%)

**프로필 요약:**
- 플랫폼: {platforms}
- 팔로워: {followers}
- 평균 참여율: {engagement_rate}%
- 주요 카테고리: {categories}

**추천 이유:**
1. [카테고리] {구체적 이유}
2. [오디언스] {구체적 이유}
3. [성과] {구체적 이유}

**예상 성과:**
- 예상 조회수: {views}
- 예상 참여율: {engagement_rate}%
- 예상 저장수: {saves}
- ROI: {cost_per_engagement}원/참여

**협업 제안:**
- 추천 플랫폼: {platform}
- 추천 포맷: {format}
- 협상 포인트: {negotiation_tip}
- 총 비용: {total_cost}원

**주의 사항:**
- {risk_factors}

---

### 2위: @{handle} (적합도 {score}%)
...

### 3위: @{handle} (적합도 {score}%)
...

---

## 번들 협업 제안

여러 크리에이터를 조합한 최적 전략:

**옵션 A: 고성과 집중형**
- 크리에이터: 1위 + 2위
- 총 비용: {cost}
- 예상 총 도달: {reach}
- 특징: 높은 참여율, 브랜드 적합성 우수

**옵션 B: 효율 극대화형**
- 크리에이터: 2위 + 3위
- 총 비용: {cost}
- 예상 총 도달: {reach}
- 특징: 비용 효율적, 다양한 오디언스

**추천:** {recommended_option}
- 이유: {reason}
```

## 평가 세부 기준

### 카테고리 적합성 (25%)
- 완벽 일치 (주력 카테고리): 100점
- 높은 관련성 (서브 카테고리): 80점
- 중간 관련성 (유사 카테고리): 60점
- 낮은 관련성: 40점 이하

### 오디언스 일치도 (25%)
- 연령대 완전 포함: 40점
- 성별 일치: 30점
- 지역 일치: 20점
- 관심사 일치: 10점

### 참여율 (20%)
- 상위 (5% 이상): 100점
- 우수 (3-5%): 80점
- 보통 (1-3%): 60점
- 저조 (1% 미만): 40점

### 가격 효율성 (15%)
- CPE(Cost Per Engagement) 기준
- 낮을수록 높은 점수

### 협업 신뢰도 (15%)
- 과거 미션 완수율
- 평균 성과 대비 실제 성과
- 납기 준수율
- 브랜드 세이프티 이슈

## 예시 출력

### 1위: @eco_beauty_lover (적합도 95%)

**프로필 요약:**
- 플랫폼: Instagram, TikTok
- 팔로워: 52K (인스타) / 128K (틱톡)
- 평균 참여율: 4.8% (인스타) / 6.2% (틱톡)
- 주요 카테고리: 뷰티, 지속가능성, 라이프스타일

**추천 이유:**
1. [카테고리] 친환경, 클린뷰티 콘텐츠 전문으로 미션 주제 완벽 일치
2. [오디언스] Z세대 여성 85%, 서울/경기 집중으로 타겟 정확
3. [성과] 최근 6개월 평균 참여율 5.2%로 카테고리 상위 10%

**예상 성과:**
- 예상 조회수: 45,000 (인스타 릴스 기준)
- 예상 참여율: 5.5%
- 예상 저장수: 2,250
- ROI: 178원/참여

**협업 제안:**
- 추천 플랫폼: 인스타 릴스 (타겟 집중도 높음)
- 추천 포맷: 언박싱 + 재활용 팁
- 협상 포인트: 인스타+틱톡 번들 시 10% 할인 가능
- 총 비용: 360,000원 (번들 할인 적용)

**주의 사항:**
- 12월 말 휴가 예정, 납기 여유 필요
"""
```

---

## 3. 프롬프트 사용 함수

```python
def generate_mission_from_insight(insight: dict) -> str:
    """인사이트에서 미션 생성 프롬프트 실행"""
    import json

    prompt = INSIGHT_TO_MISSION_PROMPT.format(
        insight_json=json.dumps(insight, ensure_ascii=False, indent=2),
        insight_id=insight.get('insight_id', 'unknown')
    )

    # LLM API 호출
    # response = llm.invoke(prompt)
    # return response

    return prompt


def match_creators_to_mission(mission: dict, creators: list) -> str:
    """미션에 맞는 크리에이터 매칭 프롬프트 실행"""
    import json

    prompt = MISSION_TO_CREATOR_PROMPT.format(
        mission_json=json.dumps(mission, ensure_ascii=False, indent=2),
        creators_json=json.dumps(creators, ensure_ascii=False, indent=2)
    )

    # LLM API 호출
    # response = llm.invoke(prompt)
    # return response

    return prompt
```

---

## 4. 통합 워크플로우

```python
async def insight_to_campaign_workflow(insight: dict, creators_pool: list):
    """인사이트 → 미션 → 크리에이터 전체 워크플로우"""

    # Step 1: 인사이트에서 미션 생성
    mission_prompt = generate_mission_from_insight(insight)
    mission = await llm.ainvoke(mission_prompt)

    # Step 2: 미션에 맞는 크리에이터 매칭
    matching_prompt = match_creators_to_mission(mission, creators_pool)
    recommendations = await llm.ainvoke(matching_prompt)

    return {
        "insight": insight,
        "mission": mission,
        "creator_recommendations": recommendations
    }
```

---

## 5. n8n 자동화 연동

```json
{
  "name": "Insight to Campaign Automation",
  "nodes": [
    {
      "name": "New Insight Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "insight-to-campaign"
      }
    },
    {
      "name": "Generate Mission",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "{{ $env.API_URL }}/api/mission/generate",
        "method": "POST",
        "body": "={{ $json.insight }}"
      }
    },
    {
      "name": "Match Creators",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "{{ $env.API_URL }}/api/creator/match",
        "method": "POST",
        "body": "={{ $json.mission }}"
      }
    },
    {
      "name": "Send to Slack",
      "type": "n8n-nodes-base.slack",
      "parameters": {
        "channel": "#campaign-planning",
        "text": "새로운 캠페인 기회!\n\n인사이트: {{ $json.insight.title }}\n미션: {{ $json.mission.title }}\n추천 크리에이터: {{ $json.recommendations[0].name }}"
      }
    }
  ]
}
```

---

## 참고 문서

- [domain_mission_creator.md](domain_mission_creator.md) - 도메인 모델 정의
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - 시스템 개요
