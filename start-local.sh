#!/usr/bin/env bash
# Start ClosedTabs WITHOUT Docker (Mac / Linux, needs Python 3.10+).
# Usage:  bash start-local.sh      Stop: press Ctrl + C (or close the window)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/app"

PY=$(command -v python3 || true)
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo "✗ Needs Python 3.10 or newer. Install it from https://www.python.org/downloads/ (or use: bash start.sh with Docker)"
  exit 1
fi

# One-time install (and again whenever requirements change)
if [ ! -x .venv/bin/uvicorn ] || [ requirements.txt -nt .venv/.installed ]; then
  echo "→ Installing (one time, about a minute)…"
  [ -d .venv ] || "$PY" -m venv .venv
  .venv/bin/pip install -q --disable-pip-version-check -r requirements.txt
  touch .venv/.installed
fi

# Settings: Claude key + model from deploy/.env (same file the Docker version uses)
[ -f "$ROOT/deploy/.env" ] || cp "$ROOT/deploy/.env.example" "$ROOT/deploy/.env"
set -a; . "$ROOT/deploy/.env"; set +a

export DATA_DIR="$ROOT/app/data"
(sleep 2; (command -v open >/dev/null && open http://localhost:3000) || \
          (command -v xdg-open >/dev/null && xdg-open http://localhost:3000) || true) &
echo "✓ ClosedTabs: http://localhost:3000   (keep this window open; Ctrl + C to stop)"
exec .venv/bin/uvicorn closedtabs.web:app --host 127.0.0.1 --port 3000 --log-level warning
