---
description: 테스트 생성 및 커버리지 개선
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: [file or function to test]
---

# Test Generation

$ARGUMENTS에 대한 테스트를 생성하고 커버리지를 개선합니다.

## Tasks
1. 대상 코드 분석
2. pytest 유닛 테스트 생성
3. Cypress E2E 테스트 생성 (해당 시)
4. 엣지 케이스 테스트 추가
5. 커버리지 측정 및 리포트
6. CI 테스트 명령어 확인

## Standards
- pytest async 지원
- 파라미터화 테스트 활용
- 픽스처 재사용
- 80%+ 커버리지 목표
