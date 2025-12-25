#!/bin/bash
# Claude Code post-tool-use hook for auto-formatting

set -e

# Read tool input from stdin
input=$(cat)

# Extract file path from JSON input
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

if [ -z "$file_path" ]; then
  exit 0
fi

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Check if file exists
if [ ! -f "$file_path" ]; then
  exit 0
fi

# Format Python files with black and ruff
if [[ "$file_path" == *.py ]]; then
  if command -v black &> /dev/null; then
    black --quiet "$file_path" 2>/dev/null || true
  fi
  if command -v ruff &> /dev/null; then
    ruff check --fix --quiet "$file_path" 2>/dev/null || true
  fi
fi

# Format TypeScript/JavaScript with prettier
if [[ "$file_path" =~ \.(ts|tsx|js|jsx)$ ]]; then
  if command -v npx &> /dev/null; then
    npx prettier --write "$file_path" 2>/dev/null || true
  fi
fi

# Format JSON files
if [[ "$file_path" == *.json ]]; then
  if command -v npx &> /dev/null; then
    npx prettier --write "$file_path" 2>/dev/null || true
  fi
fi

exit 0
