#!/usr/bin/env bash
# Run Plot Keeper end-to-end on a single port.
# Flask serves the built frontend; Vite watches sources and rebuilds
# `backend/static` on every change. Ctrl-C stops both.
#
# Open http://localhost:5757
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ] || [ ! -d frontend/node_modules ]; then
  echo "First-run setup needed:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt" >&2
  echo "  (cd frontend && npm install)" >&2
  exit 1
fi

trap 'kill 0' INT TERM EXIT

# Initial build so the first page request has something to serve.
echo "→ initial frontend build…"
(cd frontend && npx vite build --logLevel warn)

# Watch + Flask, both in this process group so Ctrl-C kills both.
echo "→ vite watch + flask debug; open http://localhost:5757"
(cd frontend && npx vite build --watch --logLevel warn) &
.venv/bin/flask --app backend.app run --port 5757 --debug
