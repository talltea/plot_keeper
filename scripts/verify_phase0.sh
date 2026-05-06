#!/usr/bin/env bash
# Live-server smoke for phase 0. Boots Flask, hits /api/ping and /,
# tears down. Exits non-zero on any failure.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

PORT=${PORT:-5757}
LOG=$(mktemp)

.venv/bin/flask --app backend.app run --port "$PORT" --no-debug >"$LOG" 2>&1 &
FLASK_PID=$!
trap 'kill "$FLASK_PID" 2>/dev/null || true; rm -f "$LOG"' EXIT

# Wait for the port to accept connections (~6s ceiling).
for _ in $(seq 1 30); do
  if curl -sf "http://localhost:$PORT/api/ping" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

PING=$(curl -sSf "http://localhost:$PORT/api/ping")
echo "GET /api/ping → $PING"

INDEX_STATUS=$(curl -sSo /dev/null -w '%{http_code}' "http://localhost:$PORT/")
echo "GET /          → HTTP $INDEX_STATUS"

case "$PING" in
  *'"ok":true'*) ;;
  *) echo "FAIL: /api/ping body unexpected"; echo "--- flask log ---"; cat "$LOG"; exit 1 ;;
esac

if [ "$INDEX_STATUS" != "200" ]; then
  echo "FAIL: / returned HTTP $INDEX_STATUS"
  cat "$LOG"
  exit 1
fi

echo "OK"
