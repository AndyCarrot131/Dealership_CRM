#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

docker network inspect dealer_crm_net >/dev/null 2>&1 || docker network create dealer_crm_net

MODEL_DIR="$ROOT/local_model/qwen3.5-4b-instruct"
MODEL_FILE="$MODEL_DIR/qwen3.5-4b-instruct-Q4_K_M.gguf"
MMPROJ_FILE="$MODEL_DIR/mmproj-qwen3.5-4b-instruct-f16.gguf"

if [ ! -s "$MODEL_FILE" ]; then
  echo "Missing model: $MODEL_FILE" >&2
  echo "Download it from openresearchtools/Qwen3.5-4B-Instruct-GGUF before starting." >&2
  exit 1
fi

if [ ! -s "$MMPROJ_FILE" ]; then
  echo "Missing vision projector: $MMPROJ_FILE" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required (docker compose or docker-compose)." >&2
  exit 1
fi

echo "Starting Qwen3.5-4B-Instruct Q4_K_M with vision support..."
"${COMPOSE[@]}" -f docker-compose.llm.yml up -d --build

echo "Waiting for the OpenAI-compatible API..."
for attempt in {1..120}; do
  if curl --fail --silent http://localhost:8080/health >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 120 ]; then
    echo "Local LLM did not become healthy in time." >&2
    "${COMPOSE[@]}" -f docker-compose.llm.yml logs --tail=100 local_llm >&2
    exit 1
  fi
  sleep 2
done

echo ""
echo "Local LLM is running at http://localhost:8080/v1"
echo "Model: local_model/qwen3.5-4b-instruct/qwen3.5-4b-instruct-Q4_K_M.gguf"
