---
name: review
description: PR 코드 리뷰 수행. 코드 품질, 테스트 커버리지, 보안, 베스트 프랙티스 검토
allowed-tools: Read, Grep, Glob, Bash
---

# Pull Request Review

## Instructions
1. PR diff 및 변경 파일 가져오기
2. 변경사항 리뷰:
   - 코드 품질 및 스타일
   - 테스트 커버리지
   - 성능 영향
   - 보안 이슈
   - 문서 업데이트
3. 건설적인 피드백 제공
4. 개선사항 제안

## Review Checklist
- [ ] 코드 스타일 일관성
- [ ] 적절한 에러 핸들링
- [ ] 충분한 테스트 커버리지
- [ ] 문서 업데이트
- [ ] 하드코딩된 시크릿 없음
- [ ] async/await 패턴 준수 (Python)
- [ ] TypeScript 타입 정의 (React)

## Output Format
```
## Summary
[변경사항 요약]

## Strengths
- [잘 된 점들]

## Suggestions
- [개선 제안들]

## Required Changes
- [필수 수정 사항]
```
