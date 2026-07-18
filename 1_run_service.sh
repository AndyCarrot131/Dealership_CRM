#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

docker network inspect dealer_crm_net >/dev/null 2>&1 || docker network create dealer_crm_net

echo "Starting CRM service (database + backend + frontend)..."
docker compose up -d --build

echo "Running database migrations..."
docker compose exec app alembic upgrade head

echo ""
echo "CRM is running:"
echo "  App (UI + API): http://localhost:8756"
echo "  API docs:       http://localhost:8756/docs"
echo "  Postgres:       localhost:15432"
