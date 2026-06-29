#!/usr/bin/env bash
# Launch dts-utils-mcp from this repository (for Cursor project-local MCP config).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UV=""
if command -v uv >/dev/null 2>&1; then
  UV="$(command -v uv)"
else
  for candidate in "$HOME/.local/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv"; do
    if [[ -x "$candidate" ]]; then
      UV="$candidate"
      break
    fi
  done
fi

if [[ -z "$UV" ]]; then
  echo "run-mcp.sh: uv not found on PATH (install: https://github.com/astral-sh/uv)" >&2
  exit 1
fi

exec "$UV" run --extra mcp dts-utils-mcp
