---
description: FastAPI 엔드포인트 최적화 실행
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: [endpoint path or file]
---

# FastAPI Optimization

$ARGUMENTS FastAPI 엔드포인트를 최적화합니다.

## Tasks
1. 대상 엔드포인트 분석
2. async/await 패턴 검토 및 수정
3. Pydantic v2 모델 최적화
4. Redis 캐싱 적용 검토
5. 에러 핸들링 개선
6. Prometheus 메트릭 추가 검토

## Standards
- async/await 필수
- Pydantic v2 ConfigDict 사용
- 타입 힌트 필수
- 캐싱 TTL 명시
