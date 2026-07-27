#!/usr/bin/env bash
# Deploy production on the Hostinger VPS (/opt/feedeo).
# Used by GitHub Actions and for manual SSH deploys.
set -euo pipefail

cd /opt/feedeo

echo "==> Fetching origin/main"
git fetch origin main
git reset --hard origin/main
echo "==> Now at $(git log -1 --oneline)"

echo "==> Building app images"
docker compose build backend worker frontend nginx scheduler

echo "==> Restarting services"
docker compose up -d backend worker frontend nginx scheduler

echo "==> Status"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Image}}"
echo "DONE"
