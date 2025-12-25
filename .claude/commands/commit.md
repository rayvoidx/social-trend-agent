---
description: 변경사항 분석 후 커밋 생성
allowed-tools: Bash, Read, Grep
---

# Smart Commit

현재 변경사항을 분석하고 적절한 커밋 메시지를 생성합니다.

## Tasks
1. `git status`로 변경사항 확인
2. `git diff`로 상세 변경 내용 분석
3. 변경 유형 파악 (feat, fix, refactor, docs, test, chore)
4. Conventional Commits 형식으로 메시지 작성
5. 사용자 확인 후 커밋 실행

## Commit Format
```
<type>(<scope>): <subject>

<body>

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Types
- feat: 새로운 기능
- fix: 버그 수정
- refactor: 리팩토링
- docs: 문서 변경
- test: 테스트 추가/수정
- chore: 빌드, 설정 변경
