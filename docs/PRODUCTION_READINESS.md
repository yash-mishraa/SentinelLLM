# SentinelLLM — Production Readiness Audit & Technical Inventory

> **Document Status:** Authoritative Technical Baseline (Milestone 1)  
> **Repository:** `https://github.com/yash-mishraa/SentinelLLM`  
> **Commit Verified:** `73a83921a47aa38a1eaec7735730eba45bb5aeea`  
> **Target Version:** `v1.0.0-rc.1`

---

## 1. Executive Summary

SentinelLLM is an open-source, defense-in-depth runtime security framework designed to protect Large Language Model (LLM) applications and autonomous AI agents. This audit establishes the concrete operational state of SentinelLLM across its backend security engine, database persistence layer, Next.js 15 operations dashboard, container packaging, and CI/CD deployment pipelines.

### Verified Readiness Status
* **Core Runtime Engine:** 100% implemented and tested (Policy Decision Point, Policy Enforcement Point, Canary Leak, Prompt Injection, Context Taint).
* **Database Persistence:** SQLAlchemy 2.0 ORM with PostgreSQL 16 migrations (Alembic `001_initial_schema`, `002_rate_limiting`) and row-level locking (`SELECT ... FOR UPDATE`).
* **REST API Gateway:** FastAPI gateway with SHA-256 API-key hashing, constant-time verification, separation of duties, and distributed sliding-window rate limiting.
* **Frontend Operations Dashboard:** Next.js 15 App Router with HttpOnly HMAC-SHA256 BFF proxy, CSRF origin validation, and zero client-side secret exposure.
* **Packaging & Containerization:** Multi-stage non-root Dockerfile (UID 10001, GID 10001) with `/healthz` and `/readyz` probes.
* **Quality Gates:** 268 backend tests (264 passed, 4 real PostgreSQL integration tests skipped locally without live DB), strict Mypy (96 source files clean), Ruff lint/format clean, 16/16 Node.js frontend security tests passed.

---

## 2. Complete Environment Variable & Configuration Trace

Every environment variable referenced across Python, TypeScript, Docker, and GitHub Actions has been traced directly to its consumer:

| Variable Name | Purpose | Classification | Status | Safe Default | Consumer in Codebase | Destination | Failure Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | Secret | Mandatory in Prod | `sqlite:///sentinelllm_dev.db` in dev | `src/sentinelllm/db/config.py`, `alembic/env.py`, `scripts/migrate.py` | Cloud Run, GitHub Secrets | Raises `ValueError` in production; prevents migrations |
| `SENTINELLLM_DATABASE_URL` | Explicit Sentinel-prefixed DB URL alias | Secret | Optional Alias | Falls back to `DATABASE_URL` | `src/sentinelllm/db/config.py`, `alembic/env.py` | Cloud Run, Local `.env` | Falls back to `DATABASE_URL` |
| `SENTINELLLM_ENV` | Runtime mode (`development`, `staging`, `production`) | Config | Mandatory in Prod | `"development"` | `src/sentinelllm/api/auth.py`, `src/sentinelllm/db/config.py` | Cloud Run, GitHub Actions | Defaults to `"development"` (dev keys permitted) |
| `SENTINELLLM_ADMIN_KEY` | Admin role API key (`*` permissions) | Secret | Mandatory in Prod | `"sentinel-admin-key-secret"` (dev only) | `src/sentinelllm/api/auth.py`, `web/src/lib/session.ts`, `scripts/smoke_test.py` | Cloud Run, Vercel, GitHub Secrets | Raises `ValueError` in production if missing/dev default |
| `SENTINELLLM_SUPERVISOR_KEY` | Supervisor role API key (`approvals:manage`) | Secret | Mandatory in Prod | `"sentinel-supervisor-key-secret"` (dev only) | `src/sentinelllm/api/auth.py`, `web/src/lib/session.ts` | Cloud Run, Vercel | Raises `ValueError` in production if missing/dev default |
| `SENTINELLLM_ANALYST_KEY` | Analyst role API key (`inspect`, `authorize`) | Secret | Mandatory in Prod | `"sentinel-analyst-key-secret"` (dev only) | `src/sentinelllm/api/auth.py`, `web/src/lib/session.ts` | Cloud Run, Vercel | Raises `ValueError` in production if missing/dev default |
| `SENTINELLLM_GUEST_KEY` | Guest role API key (read-only inspection) | Secret | Mandatory in Prod | `"sentinel-guest-key-secret"` (dev only) | `src/sentinelllm/api/auth.py`, `web/src/lib/session.ts`, `scripts/smoke_test.py` | Cloud Run, Vercel, GitHub Secrets | Raises `ValueError` in production if missing/dev default |
| `SENTINELLLM_API_KEYS` | JSON string defining arbitrary dynamic key records | Secret (JSON) | Optional | None | `src/sentinelllm/api/auth.py` | Cloud Run, Secret Manager | Logged as error; falls back to individual role keys |
| `SESSION_SECRET` | HMAC-SHA256 signing secret for session cookies | Secret | Mandatory in Prod | `"dev-session-signing-secret-random-32chars"` | `web/src/lib/session.ts` | Vercel (Production & Preview) | Throws 500 error in production if `< 32` chars |
| `SENTINELLLM_API_URL` | Canonical HTTPS URL of backend gateway | URL | Mandatory in Prod | `"http://127.0.0.1:8000"` | `web/src/app/api/backend/[...path]/route.ts` | Vercel (Production & Preview) | BFF proxy returns HTTP 503 Service Unavailable |
| `BACKEND_URL` | Alias for `SENTINELLLM_API_URL` | URL | Optional Alias | Falls back to `SENTINELLLM_API_URL` | `web/src/app/api/backend/[...path]/route.ts` | Vercel (Production & Preview) | Falls back to `SENTINELLLM_API_URL` |
| `SENTINELLLM_CORS_ORIGINS` | Trusted origins for cross-origin requests | Config (JSON) | Optional | `["http://localhost:3000"]` | `src/sentinelllm/api/config.py`, `src/sentinelllm/api/app.py` | Cloud Run | Disallows direct cross-origin browser requests |
| `SENTINELLLM_MAX_REQUEST_SIZE_BYTES` | Request body size limit in bytes | Config | Optional | `1048576` (1 MB) | `src/sentinelllm/api/config.py`, `src/sentinelllm/api/app.py` | Cloud Run | Rejects payloads over 1 MB with HTTP 413 |
| `SENTINELLLM_RATE_LIMIT_ENABLED` | Toggle distributed database rate limiting | Config | Optional | `true` | `src/sentinelllm/api/config.py`, `src/sentinelllm/api/rate_limiter.py` | Cloud Run | Rate limiting disabled if set to false |
| `SENTINELLLM_RATE_LIMIT_PER_MINUTE` | Rate limit threshold per minute per bucket | Config | Optional | `60` | `src/sentinelllm/api/config.py`, `src/sentinelllm/api/rate_limiter.py` | Cloud Run | Rejects requests exceeding threshold with HTTP 429 |
| `PORT` | Container internal listening port | Identifier | Injected by Host | `8000` | `scripts/entrypoint.sh`, `Dockerfile` | Cloud Run runtime | Binds to 8000 |
| `WORKERS` | Uvicorn worker process count | Config | Optional | `2` | `scripts/entrypoint.sh` | Cloud Run | Runs 2 worker processes |
| `OPENAI_API_KEY` | Optional key for live LLM inference | Secret | Optional | None (Offline `FakeLLMAdapter` default) | `src/sentinelllm/adapters/openai.py` | Cloud Run / Local `.env` | Throws `SafetyOptInRequiredError` or `AuthenticationError` |
| `POSTGRES_TEST_URL` | Connection URL for integration test suite | Secret | Optional in dev | Ephemeral container URL in CI | `tests/integration/test_postgres_integration.py` | GitHub Actions runner | Tests skipped with note if unset locally |
| `GCP_SA_KEY` | Service Account JSON key for Cloud Run CD | Secret | Required for CD | None | `.github/workflows/deploy.yml` | GitHub Secrets | Cloud Run deployment step fails |
| `GCP_SERVICE_NAME` | Cloud Run service name | Identifier | Required for CD | None | `.github/workflows/deploy.yml` | GitHub Variables | Deployment step fails |
| `GCP_REGION` | Google Cloud region | Identifier | Required for CD | `"us-central1"` | `.github/workflows/deploy.yml` | GitHub Variables | Deployment step fails |
| `CONTAINER_PROVIDER` | Selected container orchestrator | Identifier | Required for CD | None | `.github/workflows/deploy.yml` | GitHub Variables | Skips container deployment step |
| `BACKEND_API_URL` | Cloud Run URL for workflow health checks | URL | Required for CD | None | `.github/workflows/deploy.yml` | GitHub Variables | Workflow `/readyz` probe fails |
| `VERCEL_TOKEN` | Vercel automation token for headless deployment | Secret | Required for CD | None | `.github/workflows/deploy.yml` | GitHub Secrets | Vercel deployment step fails |
| `VERCEL_ORG_ID` | Vercel Organization / Team ID | Identifier | Required for CD | None | `.github/workflows/deploy.yml` | GitHub Secrets / Env | Vercel CLI fails to link project |
| `VERCEL_PROJECT_ID` | Vercel Project ID | Identifier | Required for CD | None | `.github/workflows/deploy.yml` | GitHub Secrets / Env | Vercel CLI fails to link project |

---

## 3. Deployment Blockers & Actionable Resolutions

### Category 1: Remote CI
* **Status:** **CLEAN (0 Blockers)**. All tests run self-contained on Ubuntu 22.04 runners using Python 3.12/3.13, Node 20, and a local PostgreSQL 16 Alpine service container.

### Category 2: Staging Deployment Prerequisites
1. **Cloud Run Private Image Access from GHCR:**
   * *Detail:* Container images pushed to GitHub Container Registry (`ghcr.io/yash-mishraa/sentinelllm/backend`) inherit private visibility by default. Cloud Run cannot pull images across trust boundaries without authentication.
   * *Resolution:* Grant the GHCR package public read permission, OR configure a Google Artifact Registry push target in GCP.
2. **Vercel Project Association:**
   * *Detail:* Headless CI deployment via `vercel pull` requires `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID`.
   * *Resolution:* Configure both variables in GitHub Secrets/Variables, or use native Vercel GitHub integration.
3. **Cloud Run Ingress Settings:**
   * *Detail:* Cloud Run defaults to requiring IAM authorization (`--no-allow-unauthenticated`). The Next.js BFF proxy on Vercel communicates over public HTTPS with backend API keys.
   * *Resolution:* Set Cloud Run ingress to *Allow all traffic* and authentication to *Allow unauthenticated invocations*.

### Category 3: Production Deployment Prerequisites
1. **Neon Connection String Mode:**
   * *Detail:* Neon offers pooled (PgBouncer) and direct connection strings. Database migrations (`scripts/migrate.py`) require the **direct unpooled connection** on port 5432 to execute transactional DDL.
   * *Resolution:* Use direct connection for migration jobs; runtime backend containers can use either direct or pooled with `pool_pre_ping=True`.
2. **GitHub Protected Environment Approval:**
   * *Detail:* GitHub Environments must have **Required reviewers** enabled for `production`.
   * *Resolution:* Add your GitHub account under Environment Protection Rules.
3. **High-Entropy Production Secrets:**
   * *Detail:* Generate independent 32+ character secrets for `SENTINELLLM_ADMIN_KEY`, `SENTINELLLM_SUPERVISOR_KEY`, `SENTINELLLM_ANALYST_KEY`, `SENTINELLLM_GUEST_KEY`, and `SESSION_SECRET`.

---

## 4. Acceptance Criteria & Verification Evidence

| Domain | Invariant | Local Verification | CI Verification | Production Verification |
| :--- | :--- | :---: | :---: | :---: |
| **Migrations** | Forward upgrade to HEAD | `scripts/migrate.py` (Clean) | `postgres-integration` (Clean) | Manual verification on Neon |
| **Authentication** | SHA-256 verifier, constant-time compare | `test_api.py` (Clean) | Matrix 3.12 / 3.13 (Clean) | `smoke_test.py` (Clean) |
| **Dual Custody** | Requester cannot approve own action | `test_approvals.py` (Clean) | Unit suite (Clean) | Enforced at PDP |
| **Row-Level Locking** | Atomic approval consumption | PostgreSQL concurrency test | Automated in CI | Tested in staging |
| **Session Security** | HMAC-SHA256, HttpOnly, SameSite=lax | 16/16 Node tests (Clean) | Bundle scan (Clean) | Live browser check |
| **Rate Limiter** | Distributed sliding window | `test_api_security.py` (Clean) | Postgres backed | Enforced at Gateway |
| **Adversarial Benchmark** | 22/23 cases, 10/10 scenarios, 0 unauthorized | `promptprobe run` (Clean) | Deterministic runner | Visible on Dashboard |
| **Container Hardening** | Non-root UID 10001, signal preservation | Local Docker build (Clean) | `docker-validation` (Clean) | Cloud Run health probe |
