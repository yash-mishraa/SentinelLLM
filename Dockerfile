# ==============================================================================
# SentinelLLM REST Gateway — Multi-Stage Production Dockerfile
# ==============================================================================
# Security Invariants:
# 1. Multi-stage build isolation: compilers and build tools never reach production.
# 2. Strict non-root execution: runs as UID 10001 (sentinel).
# 3. Minimal surface: secrets, .env files, git history, and tests are excluded.
# 4. In-container healthcheck probing root /healthz liveness endpoint.
# 5. Signal handling: preserves SIGTERM/SIGINT for zero-downtime rolling deploys.
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Dependency & Package Builder
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY promptprobe ./promptprobe

# Build self wheel and compile binary dependencies (including PostgreSQL drivers)
RUN pip install --no-cache-dir --upgrade pip build wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels ".[postgres]"

# ------------------------------------------------------------------------------
# Stage 2: Hardened Runtime Container
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runner

# Install minimal runtime utility for Docker orchestration health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged system user and runtime directories
RUN groupadd -g 10001 sentinel && \
    useradd -u 10001 -g sentinel -s /bin/sh -m sentinel && \
    mkdir -p /app /data && \
    chown -R sentinel:sentinel /app /data

WORKDIR /app

# Install wheels generated in the builder stage
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl && \
    rm -rf /wheels

# Copy application runtime files and migration assets
COPY --chown=sentinel:sentinel alembic.ini ./
COPY --chown=sentinel:sentinel alembic ./alembic
COPY --chown=sentinel:sentinel scripts ./scripts
COPY --chown=sentinel:sentinel src ./src
COPY --chown=sentinel:sentinel promptprobe ./promptprobe
COPY --chown=sentinel:sentinel benchmarks ./benchmarks

# Enforce non-root execution
USER sentinel

# Container runtime defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    SENTINELLLM_ENV=production \
    PORT=8000 \
    WORKERS=2

EXPOSE 8000

# Container liveness check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/healthz || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
