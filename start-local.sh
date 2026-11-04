#!/usr/bin/env bash
# Start ClosedTabs WITHOUT Docker (Mac / Linux, needs Python 3.10+).
# Usage:  bash start-local.sh      Stop: press Ctrl + C (or close the window)
# Background mode (used by the autostart): CLOSEDTABS_BACKGROUND=1 — no browser, logs to app/data/closedtabs.log
set -euo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/Current/bin:$PATH"
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/app"
URL="http://localhost:3000"
BACKGROUND="${CLOSEDTABS_BACKGROUND:-}"

open_browser() {
  [ -n "$BACKGROUND" ] && return 0
  (command -v open >/dev/null && open "$URL") || (command -v xdg-open >/dev/null && xdg-open "$URL") || true
}

# Already running (e.g. started automatically)? Then just open it.
if [ -z "$BACKGROUND" ] && curl -fs -o /dev/null --max-time 2 "$URL/health" 2>/dev/null; then
  echo "✓ ClosedTabs is already running: $URL"
  open_browser
  exit 0
fi

# One-time install (and again whenever requirements change). Python is only needed here.
if [ ! -x .venv/bin/uvicorn ] || [ requirements.txt -nt .venv/.installed ]; then
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    p=$(command -v "$c" || true)
    if [ -n "$p" ] && "$p" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null; then PY="$p"; break; fi
  done
  if [ -z "$PY" ]; then
    echo "✗ Needs Python 3.10 or newer. Install it from https://www.python.org/downloads/ (or use: bash start.sh with Docker)"
    exit 1
  fi
  echo "→ Installing (one time, about a minute)…"
  [ -d .venv ] || "$PY" -m venv .venv
  .venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
  touch .venv/.installed
fi
[ -n "${CLOSEDTABS_INSTALL_ONLY:-}" ] && exit 0

# Settings: AI keys + model from deploy/.env (same file the Docker version uses)
[ -f "$ROOT/deploy/.env" ] || cp "$ROOT/deploy/.env.example" "$ROOT/deploy/.env"
set -a; . "$ROOT/deploy/.env"; set +a

export DATA_DIR="$ROOT/app/data"
mkdir -p "$DATA_DIR"
if [ -n "$BACKGROUND" ]; then
  exec .venv/bin/uvicorn closedtabs.web:app --host 127.0.0.1 --port 3000 --log-level warning \
    >>"$DATA_DIR/closedtabs.log" 2>&1
fi
(sleep 2; open_browser) &
echo "✓ ClosedTabs: $URL   (keep this window open; Ctrl + C to stop)"
exec .venv/bin/uvicorn closedtabs.web:app --host 127.0.0.1 --port 3000 --log-level warning
