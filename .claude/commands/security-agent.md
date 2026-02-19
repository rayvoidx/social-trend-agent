---
description: 보안 취약점 점검 및 수정
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: [component or security concern]
---

# Security Agent

$ARGUMENTS에 대한 보안 점검을 수행하고 취약점을 수정합니다.

## Tasks

1. 대상 코드 보안 스캔
2. OWASP Top 10 기준 취약점 분류
3. 심각도별 우선순위 지정
4. 수정 코드 작성 및 적용
5. 수정 후 재검증

## Focus

- 시크릿 노출 방지
- 입력 검증 (Pydantic)
- API 인증/인가
- 의존성 보안 (pip/npm audit)
- Docker 컨테이너 보안
- 프롬프트 인젝션 방어
