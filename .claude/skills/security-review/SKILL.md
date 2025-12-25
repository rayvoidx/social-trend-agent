---
name: security-review
description: 보안 리뷰 수행. 취약점 점검, OWASP Top 10, 시크릿 노출, 의존성 보안 검토
allowed-tools: Read, Grep, Glob, Bash
---

# Security Review

## Instructions
1. 변경된 모든 파일 식별
2. 보안 이슈 분석:
   - 노출된 자격 증명 또는 시크릿
   - SQL 인젝션 취약점
   - XSS 취약점
   - CSRF 취약점
   - 인증/인가 이슈
   - 데이터 노출 위험
3. 의존성 취약점 검사
4. 환경 변수 처리 검토
5. 심각도 레벨별 발견사항 문서화

## Focus Areas
- 민감 파일 보호 (.env, keys)
- 입력 검증
- 출력 인코딩
- 암호화 사용
- API 보안
- Docker 보안 설정

## OWASP Top 10 Checklist
- [ ] A01: Broken Access Control
- [ ] A02: Cryptographic Failures
- [ ] A03: Injection
- [ ] A04: Insecure Design
- [ ] A05: Security Misconfiguration
- [ ] A06: Vulnerable Components
- [ ] A07: Authentication Failures
- [ ] A08: Data Integrity Failures
- [ ] A09: Logging Failures
- [ ] A10: SSRF

## Output Format
```
## Security Review Report

### Critical
- [심각한 이슈]

### High
- [높은 위험 이슈]

### Medium
- [중간 위험 이슈]

### Low
- [낮은 위험 이슈]

### Recommendations
- [권장 조치사항]
```
