#!/usr/bin/env bash
# Re-record assets/demo.gif. Prefers vhs (https://github.com/charmbracelet/vhs)
# with assets/demo.tape; falls back to a pure-Python renderer (Rich + resvg + Pillow).
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v vhs >/dev/null 2>&1; then
  vhs assets/demo.tape
else
  echo "vhs not found: using the Python renderer (scripts/render_demo.py)" >&2
  uv run python scripts/render_demo.py
fi
