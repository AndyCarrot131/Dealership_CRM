#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

docker network inspect dealer_crm_net >/dev/null 2>&1 || docker network create dealer_crm_net

echo "Starting local LLM container..."
docker compose -f docker-compose.llm.yml up -d --build

echo ""
echo "Local LLM is running at http://localhost:8080/v1"
echo "Ensure model files are present in local_model/qwen3-vl-4b/ (see launch.sh for download instructions)."
