---
description: GitHub Actions CI/CD 파이프라인 관리 및 최적화
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: [workflow name or CI/CD task]
---

# CI/CD Agent

$ARGUMENTS에 대한 CI/CD 파이프라인을 분석하고 최적화합니다.

## Tasks

1. 기존 워크플로우 파일 분석 (.github/workflows/)
2. 빌드 시간 및 캐싱 전략 검토
3. 워크플로우 최적화 또는 신규 생성
4. 시크릿 관리 및 환경 변수 보안 확인
5. 테스트 및 배포 파이프라인 검증

## Workflows

- ci.yml: Frontend + Python CI
- test.yml: Matrix testing (3.11/3.12)
- docker.yml: Docker build & GHCR push
- lint.yml: Code quality
- claude.yml: Claude Code automation
