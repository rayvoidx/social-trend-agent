---
description: Docker 설정 최적화 및 보안 강화
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: [dockerfile or service name]
---

# Docker Optimization

$ARGUMENTS Docker 설정을 최적화하고 보안을 강화합니다.

## Tasks
1. 대상 Docker 파일 분석
2. 멀티스테이지 빌드 적용/개선
3. 헬스체크 설정 추가/개선
4. 이미지 크기 최적화
5. 보안 설정 강화
6. docker-compose 의존성 검토

## Standards
- 멀티스테이지 빌드 필수
- HEALTHCHECK 필수
- 비root 사용자 권장
- slim/alpine 베이스 이미지
