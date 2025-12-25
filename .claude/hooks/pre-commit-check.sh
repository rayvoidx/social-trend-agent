#!/bin/bash
# Claude Code pre-tool-use hook for commit safety checks

set -e

# Read tool input from stdin
input=$(cat)

# Extract command from JSON input
tool_name=$(echo "$input" | jq -r '.tool_name // empty' 2>/dev/null)
command=$(echo "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only check Bash commands
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

# Block dangerous git commands
if [[ "$command" =~ git\ push.*--force ]]; then
  echo '{"error": "Force push is blocked. Use regular push or request explicit permission."}' >&2
  exit 1
fi

if [[ "$command" =~ git\ reset.*--hard ]]; then
  echo '{"error": "Hard reset is blocked. This may cause data loss."}' >&2
  exit 1
fi

if [[ "$command" =~ rm\ -rf\ / ]] || [[ "$command" =~ rm\ -rf\ \* ]]; then
  echo '{"error": "Dangerous rm command blocked."}' >&2
  exit 1
fi

exit 0
