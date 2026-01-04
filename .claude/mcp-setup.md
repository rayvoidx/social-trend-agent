# Claude Code 자동화 설정 가이드

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                        자동 개발 워크플로우                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   [로컬 Claude Code]          [GitHub Action 레인]               │
│        ↓                           ↓                            │
│   빠른 반복 개발              @claude 멘션 → 자동 개발             │
│        ↓                           ↓                            │
│   Hooks 알림 발사              PR 생성/업데이트                    │
│        ↓                           ↓                            │
│   ┌──────────┐                ┌──────────┐                      │
│   │  Slack   │ ←──────────────│  Slack   │                      │
│   │ Webhook  │   통합 알림    │ Webhook  │                      │
│   └──────────┘                └──────────┘                      │
│        ↓                                                        │
│   📱 모바일 푸시 알림                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Slack Webhook 설정 (알림용)

### Incoming Webhook 생성
1. https://api.slack.com/apps 접속
2. "Create New App" → "From scratch"
3. App Name: `Claude Code Notifier`
4. **Incoming Webhooks** 메뉴 → 활성화
5. "Add New Webhook to Workspace" 클릭
6. 알림 받을 채널 선택 (예: `#dev-notifications`)
7. Webhook URL 복사

### 환경변수 설정
```bash
# ~/.zshrc 또는 ~/.bashrc에 추가
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../xxx"
```

또는 `.claude/settings.local.json` 사용:
```json
{
  "env": {
    "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  }
}
```

---

## 2. GitHub Secrets 설정 (Action용)

GitHub Repository → Settings → Secrets and variables → Actions:

| Secret Name | 설명 |
|-------------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 키 (필수) |
| `SLACK_WEBHOOK_URL` | Slack Webhook URL (선택) |

---

## 3. Hooks 동작 방식

### Notification Hook
Claude가 입력이나 권한을 기다릴 때 Slack으로 알림:
```
🔔 [social-trend-agent] Notification
> Claude Code session update
2025-01-03 18:45:00
```

### PostToolUse Hook
파일 수정 후 자동 포맷:
- Python: `black` + `ruff`
- TypeScript/JavaScript: `prettier`
- JSON/YAML/Markdown: `prettier`

---

## 4. GitHub Action 사용법

### 이슈에서 @claude 멘션
```markdown
# 이슈 제목: 사용자 인증 API 추가

@claude 다음 기능을 구현해주세요:

## 요구사항
- POST /api/auth/login 엔드포인트
- JWT 토큰 발급
- Redis 세션 저장

## Acceptance Criteria
- [ ] 로그인 성공 시 JWT 반환
- [ ] 잘못된 자격증명 시 401 에러
- [ ] 테스트 커버리지 80% 이상
```

### PR 리뷰에서 @claude 멘션
```markdown
@claude 이 PR의 보안 취약점을 검토해주세요
```

---

## 5. 모바일 운영 루틴

1. **📱 폰에서 이슈 생성** → @claude 트리거
2. **🔔 Slack 푸시 알림** → 진행 상황 확인
3. **✅ PR 생성 알림** → 리뷰 후 승인
4. **🖥️ 로컬 개발** → 빠른 수정/실험만

---

## 6. MCP 서버 (선택)

`.mcp.json`에 정의된 MCP 서버:

| 서버 | 용도 |
|------|------|
| `filesystem` | 프로젝트 파일 접근 |
| `github` | GitHub API 연동 |

MCP 추가:
```bash
claude mcp add <server-name>
```

---

## 7. 파일 구조

```
.claude/
├── settings.json          # Hooks + Permissions 설정
├── settings.local.json    # 개인 환경변수 (gitignore)
├── hooks/
│   ├── notify_slack.sh    # Slack 알림 스크립트
│   └── format_after_edit.sh # 자동 포맷 스크립트
├── agents/
│   ├── planner.md
│   ├── api-agent.md
│   ├── web-agent.md
│   ├── docker-agent.md
│   └── test-agent.md
└── commands/
    └── *.md

.github/workflows/
└── claude.yml             # Claude Code Action
```

---

## 8. 테스트

### Slack 알림 테스트
```bash
echo '{"hook_event_name": "Notification", "notification": {"message": "Test message"}}' | \
  SLACK_WEBHOOK_URL="your-webhook-url" \
  CLAUDE_PROJECT_DIR="$(pwd)" \
  .claude/hooks/notify_slack.sh
```

### GitHub Action 테스트
1. 이슈 생성: "Test: @claude ping"
2. Action 실행 확인: Actions 탭
3. Slack 알림 수신 확인
