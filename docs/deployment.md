# SentinelLLM — Production Deployment & Operations Guide

This guide details the deployment architecture, configuration, database migrations, CI/CD pipelines, and post-deployment verification for SentinelLLM.

---

## 1. Target Architecture Overview

SentinelLLM is architected into three independently scalable tiers:

```mermaid
flowchart TD
    UserBrowser["End-User Browser"]
    Vercel["Next.js 15 Frontend (Vercel)<br/>BFF Session Proxy & Cookie Auth"]
    Backend["FastAPI Security Gateway (Fly.io / Cloud Run)<br/>Multi-Stage Container (Non-root UID 10001)"]
    Postgres["Managed PostgreSQL (Neon / Cloud SQL)<br/>Pooled & SSL Enforced"]
    LLM["Optional Live LLM Provider<br/>(Gemini / OpenAI / Anthropic)"]

    UserBrowser -->|"HTTPS (HttpOnly Cookie)"| Vercel
    Vercel -->|"mTLS / HTTPS + X-API-Key"| Backend
    Backend -->|"SQLAlchemy 2.0 (SSL Required)"| Postgres
    Backend -.->|"Provider-Neutral SDK"| LLM
```

### Hosting Recommendations

| Tier | Primary Recommendation | Alternative | Rationale |
| :--- | :--- | :--- | :--- |
| **Backend Gateway** | **Fly.io** | **GCP Cloud Run** | Native Docker support, seamless private networking to Postgres, fast cold starts, and explicit release command execution. |
| **Relational Database** | **Neon** | **AWS RDS / Cloud SQL** | Serverless PostgreSQL 16, connection pooling out-of-the-box, branchable databases for staging, and SSL enforcement. |
| **Web Dashboard** | **Vercel** | **Cloudflare Pages** | Native Next.js 15 App Router support, automatic HTTPS, global edge caching, and server-side secret isolation. |

---

## 2. Traceable Environment Variable Configuration Matrix

Never expose backend API keys or database credentials to client-side code. All variables prefixed with `NEXT_PUBLIC_` are bundled into client JavaScript; SentinelLLM uses **zero** `NEXT_PUBLIC_` secret variables.

### Backend API Container (Fly.io / Google Cloud Run)

| Variable | Description | Required | Source / Default |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` or `SENTINELLLM_DATABASE_URL` | PostgreSQL connection string with SSL required. | Yes in Prod | `postgresql://user:pass@ep-host.neon.tech/sentinelllm?sslmode=require` |
| `DATABASE_POOL_SIZE` | SQLAlchemy connection pool size. | No | `5` |
| `DATABASE_MAX_OVERFLOW`| SQLAlchemy pool overflow limit. | No | `10` |
| `DATABASE_POOL_TIMEOUT` | Pool checkout timeout in seconds. | No | `30.0` |
| `SENTINELLLM_ADMIN_KEY` | Admin API key for full system access and benchmarks. | Yes in Prod | High-entropy hex secret (32+ chars) |
| `SENTINELLLM_SUPERVISOR_KEY` | Supervisor API key for approval workflow actions. | Yes in Prod | High-entropy hex secret (32+ chars) |
| `SENTINELLLM_ANALYST_KEY` | Analyst API key for policy evaluations & exports. | Yes in Prod | High-entropy hex secret (32+ chars) |
| `SENTINELLLM_GUEST_KEY` | Guest API key for unprivileged inspection probes. | No | High-entropy hex secret (32+ chars) |
| `SENTINELLLM_API_KEYS` | JSON alternative for provisioning multiple dynamic API keys. | No | `[{"raw_key":"...","principal_id":"...","roles":["admin"],"permissions":["*"]}]` |
| `SENTINELLLM_CORS_ORIGINS` | JSON list or comma-separated origins allowed for CORS. | No | `["https://sentinelllm.vercel.app"]` |
| `SENTINELLLM_RATE_LIMIT_ENABLED`| Enable database-backed distributed sliding-window rate limiting. | No | `true` |
| `SENTINELLLM_RATE_LIMIT_PER_MINUTE` | Rate limit threshold per minute. | No | `60` |
| `PORT` | Listening port inside container. | No | `8000` |
| `WORKERS` | Uvicorn worker process count. | No | `2` |
| `GEMINI_API_KEY` | API key for optional Gemini Live Provider adapter. | No | Unset (adapter disabled) |

### Frontend Web BFF (Vercel)

| Variable | Description | Required | Source / Default |
| :--- | :--- | :--- | :--- |
| `SENTINELLLM_API_URL` | Canonical URL of the FastAPI backend. | Yes in Prod | `https://sentinelllm-api.fly.dev` |
| `BACKEND_URL` | Accepted as an alias for `SENTINELLLM_API_URL`. | Alias | Fallback if `SENTINELLLM_API_URL` unset |
| `SENTINELLLM_ADMIN_KEY` | Backend API key matching the admin role. | Yes in Prod | High-entropy secret (server-side only) |
| `SENTINELLLM_SUPERVISOR_KEY` | Backend API key matching the supervisor role. | Yes in Prod | High-entropy secret (server-side only) |
| `SENTINELLLM_ANALYST_KEY` | Backend API key matching the analyst role. | Yes in Prod | High-entropy secret (server-side only) |
| `SENTINELLLM_GUEST_KEY` | Backend API key matching the guest role. | Yes in Prod | High-entropy secret (server-side only) |
| `SESSION_SECRET` | 32+ character entropy string for HMAC-SHA256 session token signatures. | Yes in Prod | Cryptographic random hex (32 bytes) |
| `NODE_ENV` | Node runtime environment. | Yes in Prod | `production` |

---

## 3. Database Migration & Rollback Runbook

SentinelLLM enforces strict separation of lifecycle: **application container startup never runs migrations**. This prevents concurrency race conditions and schema deadlocks when scaling across multiple container instances.

### Migration Lifecycle CLI

Migrations are managed via Alembic and executed using the standalone `scripts/migrate.py` utility.

```bash
# 1. Check current database revision and pending heads
python scripts/migrate.py current
python scripts/migrate.py heads

# 2. Upgrade to latest schema (applied during deployment release phase)
python scripts/migrate.py upgrade head

# 3. Rollback one revision (emergency rollback)
python scripts/migrate.py downgrade -1
```

### Platform-Specific Migration Execution

#### Option A: CI/CD Pipeline Release Phase (Provider-Neutral)
As configured in `.github/workflows/deploy.yml`, migrations execute in the `migrate-database` job after the Docker image is pushed but before web containers deploy. If migrations fail, the deployment immediately halts.

#### Option B: Fly.io Native Release Command
Fly.io provides native release phase execution via `fly.toml`:
```toml
# fly.toml
[deploy]
  release_command = "python scripts/migrate.py upgrade head"
```

#### Option C: Google Cloud Run Native Release Job
On GCP Cloud Run, release tasks are executed via Cloud Run Jobs rather than service containers:
```bash
# 1. Execute one-off Cloud Run migration job
gcloud run jobs execute sentinelllm-migrate --region us-central1 --wait

# 2. Proceed with service deployment only if job succeeds
gcloud run deploy sentinelllm-api --image ... --region us-central1
```

### Migration Failure Recovery & Rollback

1. **Pre-Migration Snapshot:** Before applying schema migrations to production, trigger an automated point-in-time snapshot or branch in Neon (`neonctl branches create`).
2. **Schema Rollback:** If a migration fails mid-flight, execute `python scripts/migrate.py downgrade -1` against the target database.
3. **Application Backward Compatibility:** All database migrations in SentinelLLM must be backward-compatible with the immediately preceding application version (additive changes first, deprecations in subsequent releases).

---

## 4. Multi-Stage Docker Container

The production container uses a multi-stage `Dockerfile`:
- **Builder Stage**: Builds Python wheels with build-essential tools.
- **Runner Stage**: Minimal distroless-like runtime containing only wheels, non-root user `sentinel` (UID 10001), `curl` for container health checks, and signals properly forwarded via `exec`.

### Build & Run Locally

```bash
# Build production image
docker build -t sentinelllm:latest .

# Run with local SQLite or remote PostgreSQL
docker run -d \
  --name sentinelllm-api \
  -p 8000:8000 \
  -e DATABASE_URL="sqlite:////data/sentinelllm.db" \
  -e SENTINEL_ADMIN_KEY="local-test-key" \
  sentinelllm:latest
```

### Container Health Checks

The container exposes two standardized probes:
- `/healthz`: Liveness probe. Probes whether the Uvicorn web process is responsive.
- `/readyz`: Readiness probe. Probes database connectivity (`SELECT 1`) and schema readiness before routing traffic.

---

## 5. Continuous Integration & Deployment (CI/CD)

### GitHub Actions Workflows

1. **Continuous Integration (`.github/workflows/ci.yml`)**:
   - Triggers on all pushes and pull requests to `main`.
   - **Backend Quality**: Ruff lint/format check, Mypy strict type checking, Pytest with $\ge 80\%$ test coverage.
   - **Frontend Quality**: Next.js 15 typecheck, ESLint, Vitest frontend security tests, bundle secret scan, Next.js production build.
   - **PostgreSQL 16 Integration**: Spins up a real `postgres:16-alpine` service container, runs Alembic migrations, verifies row-level locking (`SELECT ... FOR UPDATE`), transaction rollbacks, and distributed rate limiting.
   - **Demo & Benchmark**: Executes the deterministic 6-stage demo and PromptProbe single-case & multi-step scenario suite.
   - **Container Build Validation**: Builds the Dockerfile using buildx and validates image layers.

2. **Automated Deployment Pipeline (`.github/workflows/deploy.yml`)**:
   - Triggers on push to `main` or release tag.
   - Uses GitHub Environments (`staging`, `production`) with required reviewers.
   - Tags container images with immutable Git commit SHAs (no mutable `latest` tags in production).
   - Order: `build-and-push` $\to$ `migrate-database` $\to$ `deploy-backend` $\to$ `deploy-frontend` $\to$ `post-deploy-smoke-test`.

---

## 6. Automated Post-Deployment Smoke Testing

SentinelLLM includes an automated smoke test suite (`scripts/smoke_test.py`) that executes against running staging or production environments.

### Execution

```bash
# Production verification (strictly read-only and authorization denial checks)
python scripts/smoke_test.py \
  --url https://api.sentinelllm.com \
  --api-key sk-admin-xxxxxxxxxxxxxxxxxxxxxxxx \
  --guest-key sk-guest-xxxxxxxxxxxxxxxxxxxxxxx

# Staging verification (includes approval creation & rejection lifecycle)
python scripts/smoke_test.py \
  --url https://staging-api.sentinelllm.com \
  --api-key sk-admin-xxxxxxxxxxxxxxxxxxxxxxxx \
  --staging
```

### Smoke Test Suite Checks

1. `GET /healthz`: Liveness probe returns `HTTP 200`.
2. `GET /readyz`: Readiness probe returns `HTTP 200` with active DB connectivity.
3. `GET /api/v1/approvals` (No Auth): Confirms missing key returns `HTTP 401`.
4. `POST /api/v1/benchmark/run` (Guest Key): Confirms guest role returns `HTTP 403`.
5. `POST /api/v1/inspect`: Confirms prompt injection detection is functioning.
6. `POST /api/v1/authorize`: Confirms policy engine executes and denies unauthorized actions.
7. `POST /api/v1/execute`: Confirms execution proxy blocks unapproved actions.
8. `POST /api/v1/inspect` (Validation Error): Confirms schema error responses do not leak server paths or environment variables.
9. `POST /api/v1/approvals` + `POST .../reject` (*Staging only*): Confirms end-to-end persistent approval write and state transition.

---

## 7. Operational Trade-Offs & Provider Realities

1. **Free-Tier Limitations**:
   - **PostgreSQL**: Free tiers on managed providers (e.g. Neon) spin down on inactivity. This incurs a 1.5–3.0s cold start latency on first database query. For latency-critical enterprise environments, provision an always-on instance or configure keep-alive pings.
   - **Live LLMs**: Free tiers for Gemini or OpenAI have strict rate limits (RPM/TPM) and unpredictable availability. Live LLM features in SentinelLLM are strictly optional; deterministic mock engines are recommended for reliable CI and demonstration.

2. **Container Cold Starts**:
   - On GCP Cloud Run with zero minimum instances, container startup takes 2–4s. Setting `min_instances = 1` eliminates cold starts but incurs baseline cloud spend.
