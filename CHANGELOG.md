# Changelog

All notable changes to SentinelLLM are documented in this file.
The project adheres to [Semantic Versioning](https://semver.org/) and [PEP 440](https://peps.python.org/pep-0440/).

## [1.0.0-rc.1] - 2026-10-27

### Added
- **Core Security Runtime:** Dual-layer Policy Decision Point (PDP) and Policy Enforcement Point (PEP) decoupling probabilistic signal detection from deterministic action-level authorization.
- **Multi-Signal Heuristic Detectors:** Ingestion-time scanning for direct prompt injections, poisoned RAG context chunks, and synthetic canary token exfiltration.
- **Dual-Custody Approval Service:** Cryptographically bound approval request lifecycle with single-use tokens, caller-argument hash verification, and row-level locking (`SELECT ... FOR UPDATE`) in PostgreSQL.
- **REST API Gateway:** FastAPI service exposing `/api/v1/inspect`, `/api/v1/authorize`, `/api/v1/execute`, and `/api/v1/approvals` endpoints with SHA-256 API-key authentication, RBAC, and distributed sliding-window rate limiting.
- **Next.js 15 Operations Dashboard:** Operations console with HttpOnly HMAC-SHA256 BFF proxy, CSRF origin validation, path traversal guards, and role-based views.
- **Provider-Neutral LLM Adapters:** Pluggable adapter interface supporting simulated offline testing (`FakeLLMAdapter`) and live OpenAI-compatible APIs (`OpenAICompatibleAdapter`) with explicit opt-in and strict cost budget ceilings ($0.20 default, $1.00 maximum).
- **PromptProbe Evaluation Suite:** Companion evaluation harness with 23 synthetic benchmark cases (100% precision, 87.5% recall, 0.9333 F1, 1 documented false negative triage on `INJ-DIR-002`) and 10 multi-step attack scenarios (100% invariant pass rate, 0 unauthorized executions).
- **Hardened Deployment Pipeline:** Non-root multi-stage Docker container (UID 10001), standalone Alembic migration CLI, automated post-deployment smoke test runner, and fail-closed GitHub Actions workflows with isolated staging and production gates.

> [!NOTE]
> **Evaluation Scope Notice:** PromptProbe benchmark metrics reflect deterministic evaluation against synthetic offline fixtures with `FakeLLMAdapter`. No live frontier LLM provider evaluation has been performed in CI.
