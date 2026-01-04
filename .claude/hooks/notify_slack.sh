#!/usr/bin/env bash
set -euo pipefail

# Claude Code Notification Hook -> Slack
# Hook input JSON comes via stdin (schema defined in hooks reference)

payload="$(cat)"

# Exit silently if no webhook URL configured
if [[ -z "${SLACK_WEBHOOK_URL:-}" ]]; then
  exit 0
fi

# Parse hook event data
hook_event=$(echo "$payload" | jq -r '.hook_event_name // "unknown"')
message=$(echo "$payload" | jq -r '.notification.message // "Claude Code session update"')
session_id=$(echo "$payload" | jq -r '.session_id // "unknown"')

# Build Slack message with context
project_name="${CLAUDE_PROJECT_DIR##*/}"
timestamp=$(date '+%Y-%m-%d %H:%M:%S')

# Emoji based on event type
case "$hook_event" in
  "Notification")
    emoji=":bell:"
    ;;
  "PermissionRequest")
    emoji=":lock:"
    ;;
  "Stop")
    emoji=":white_check_mark:"
    ;;
  *)
    emoji=":robot_face:"
    ;;
esac

# Compose Slack message (use jq for proper JSON escaping)
slack_text="${emoji} *[${project_name}]* ${hook_event} | ${message} | ${timestamp}"

# Send to Slack using jq for proper JSON formatting
jq -n --arg text "$slack_text" '{"text":$text}' | \
  curl -s -X POST -H 'Content-Type: application/json' -d @- "$SLACK_WEBHOOK_URL" >/dev/null 2>&1 || true

exit 0
