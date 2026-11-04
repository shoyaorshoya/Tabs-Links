#!/usr/bin/env bash
# One-step local start for Mac / Linux.  Usage:  ./start.sh
set -euo pipefail
cd "$(dirname "$0")/deploy"

if ! command -v docker >/dev/null 2>&1; then
  echo "✗ Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "✗ Docker is installed but not running. Open Docker Desktop, wait for it to start, then re-run."
  exit 1
fi

if [ ! -f .env ]; then
  echo "→ Creating deploy/.env with fresh random secrets…"
  rand() { openssl rand -base64 36 | tr -d '/+=\n'; }
  sed -e "s|^NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=$(rand)|" \
      -e "s|^MEILI_MASTER_KEY=.*|MEILI_MASTER_KEY=$(rand)|" \
      .env.example > .env
  echo "  Done. Add your Claude API key later in deploy/.env (OPENAI_API_KEY=…) to switch on AI labels."
fi

echo "→ Starting Karakeep (first run downloads ~1–2 GB, give it a few minutes)…"
docker compose up -d

echo -n "→ Waiting for the app"
for _ in $(seq 1 90); do
  if curl -fs -o /dev/null http://localhost:3000; then
    echo; echo "✓ Running at http://localhost:3000. Sign up there to create your account."
    (command -v open >/dev/null && open http://localhost:3000) || \
    (command -v xdg-open >/dev/null && xdg-open http://localhost:3000) || true
    exit 0
  fi
  echo -n "."; sleep 2
done
echo; echo "Still starting. Check http://localhost:3000 in a minute, or run: docker compose -f deploy/docker-compose.yml logs web"
