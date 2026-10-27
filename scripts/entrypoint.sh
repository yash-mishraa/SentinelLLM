#!/usr/bin/env sh
set -e

# SentinelLLM Container Entrypoint
# Preserves OS process signals (SIGTERM, SIGINT) for graceful container shutdown.

PORT="${PORT:-8000}"
WORKERS="${WORKERS:-2}"

echo "[sentinelllm-entrypoint] Starting SentinelLLM API Gateway on port ${PORT} with ${WORKERS} worker(s)..."
exec uvicorn sentinelllm.api.app:app --host 0.0.0.0 --port "$PORT" --workers "$WORKERS"
