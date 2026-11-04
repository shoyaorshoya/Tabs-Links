#!/usr/bin/env bash
# Start ClosedTabs on this computer (Mac / Linux).  Usage:  bash start.sh
set -euo pipefail
cd "$(dirname "$0")/deploy"

if ! command -v docker >/dev/null 2>&1; then
  echo "✗ Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"; exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "✗ Docker isn't running. Open Docker Desktop, wait for 'Engine running', then try again."; exit 1
fi

# Settings file. Replace one left over from the earlier Karakeep setup, keeping a Claude key if it had one.
if [ -f .env ] && grep -q "NEXTAUTH_SECRET" .env; then
  old_key=$(grep -E '^OPENAI_API_KEY=sk-ant-' .env | cut -d= -f2- || true)
  mv .env .env.karakeep-old
  cp .env.example .env
  [ -n "$old_key" ] && sed -i.bak "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$old_key|" .env && rm -f .env.bak
  echo "→ Replaced the old Karakeep settings (saved as deploy/.env.karakeep-old)."
fi
[ -f .env ] || cp .env.example .env

echo "→ Starting ClosedTabs (the first time takes a few minutes)…"
docker compose up -d --build --remove-orphans

echo -n "→ Waiting for it to wake up"
for _ in $(seq 1 60); do
  if curl -fs -o /dev/null http://localhost:3000/health; then
    echo; echo "✓ ClosedTabs is running at http://localhost:3000"
    (command -v open >/dev/null && open http://localhost:3000) || \
    (command -v xdg-open >/dev/null && xdg-open http://localhost:3000) || true
    exit 0
  fi
  echo -n "."; sleep 2
done
echo; echo "Still starting. Open http://localhost:3000 in a minute. If it never loads, run:"
echo "  docker compose -f deploy/docker-compose.yml logs"
