#!/usr/bin/env bash
set -euo pipefail

# Claude Code PostToolUse Hook - Auto-format after Edit/Write
# Triggered on: Edit, Write tool completions

# Read hook input JSON from stdin
input=$(cat)

# Extract file path from tool_input
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

if [[ -z "$file_path" ]]; then
  exit 0
fi

# Check if file exists
if [[ ! -f "$file_path" ]]; then
  exit 0
fi

# Format Python files
if [[ "$file_path" == *.py ]]; then
  if command -v black &> /dev/null; then
    black --quiet "$file_path" 2>/dev/null || true
  fi
  if command -v ruff &> /dev/null; then
    ruff check --fix --quiet "$file_path" 2>/dev/null || true
  fi
fi

# Format TypeScript/JavaScript/JSX/TSX
if [[ "$file_path" =~ \.(ts|tsx|js|jsx)$ ]]; then
  if command -v npx &> /dev/null; then
    npx prettier --write --log-level error "$file_path" 2>/dev/null || true
  fi
fi

# Format JSON/YAML/Markdown
if [[ "$file_path" =~ \.(json|yaml|yml|md)$ ]]; then
  if command -v npx &> /dev/null; then
    npx prettier --write --log-level error "$file_path" 2>/dev/null || true
  fi
fi

exit 0
