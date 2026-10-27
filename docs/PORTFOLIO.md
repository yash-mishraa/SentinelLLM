# SentinelLLM — Engineering Portfolio & Technical Case Study

**Runtime Security Controls and Adversarial Defense-in-Depth for LLM Applications and AI Agents**

---

## 1. Project Summary (Portfolio Overview)

SentinelLLM is an open-source, defense-in-depth runtime security framework and evaluation harness designed to safeguard LLM applications and agentic tool-use pipelines against prompt injection, untrusted data poisoning, privilege escalation, and unauthorized actions.

Unlike conventional prompt-level guardrails that rely on probabilistic language model evaluations to block attacks, SentinelLLM **decouples probabilistic content inspection from deterministic action-level policy enforcement**. The framework treats the LLM as an untrusted computation engine: even if an adversary achieves complete prompt injection or goal hijacking, an out-of-band Policy Enforcement Point (PEP) intercepts all proposed tool invocations and validates host-authenticated permissions, human approvals, and cryptographic parameter digests before backing infrastructure or APIs can execute.

The system is implemented in Python 3.12+ (FastAPI, SQLAlchemy 2.0, Pydantic v2) and Next.js 15, backed by PostgreSQL 16 persistence, distributed rate limiting, and an empirical evaluation suite named **PromptProbe**.

---

## 2. CV / Resume Bullets (Engineering Outcomes)

Select from these tailored resume bullet options:

### Option A: LLM Security & AI Systems Engineering
> Engineered an out-of-band LLM security gateway in Python 3.12 (FastAPI, Pydantic v2, strict Mypy) decoupling probabilistic content detection from deterministic policy enforcement (PDP/PEP), guaranteeing zero unauthorized tool executions across 10 multi-step adversarial attack scenarios.

### Option B: Concurrency, Persistence & Distributed Systems
> Designed a concurrency-safe human approval workflow with PostgreSQL row-level locking (`SELECT ... FOR UPDATE`), SHA-256 canonical argument digests, and sliding-window rate limiting; proved double-spend defense and zero race conditions under concurrent worker stress tests.

### Option C: Full-Stack Security Architecture & Evaluation
> Built a full-stack security operations platform comprising a FastAPI REST gateway, a Next.js 15 dashboard with server-side BFF session isolation, and an empirical benchmark harness (**PromptProbe**) measuring precision, recall, and action enforcement invariants across 23 synthetic attack cases.

### Option D: Production Packaging & Hardened CI/CD
> Packaged an enterprise runtime container running as an unprivileged non-root user (`UID 10001`), with multi-stage Docker builds, isolated Alembic pre-deployment migrations, and a comprehensive GitHub Actions CI pipeline testing against PostgreSQL 16 service containers.

---

## 3. Technical Interview Walkthrough ("Elevator Pitch")

### How would you explain SentinelLLM in a 2-minute technical interview?

> *"Most teams attempting to secure LLM applications place guardrails inside the prompt or rely on a secondary LLM to judge the primary LLM's outputs. In cybersecurity, that's equivalent to asking the attacker to be the firewall. Language models are probabilistic; given sufficient prompt complexity, encoding, or indirect injection via retrieved RAG chunks, content filters will eventually suffer false negatives.*
>
> *With SentinelLLM, I approached this as an operating system security problem. I treated the model like userland code and built an out-of-band kernel gateway. Inbound text is tagged with strict provenance—whether it comes from a trusted developer instruction, a user prompt, or an untrusted retrieved document. When the model decides to call a tool, that request is intercepted out-of-band by a Policy Enforcement Point (PEP).*
>
> *The PEP doesn't care how confident the model was. It checks host-verified principal identity, requires explicit permissions, and routes high-risk actions to an atomic human-in-the-loop approval queue. If an approved action has its parameters tampered with in-flight, a SHA-256 argument digest mismatch blocks it. Even when content scanners fail completely, unauthorized tool execution remains at zero."*

---

## 4. Key Design Decisions & Architectural Trade-offs

| Design Decision | Chosen Approach | Alternative Considered | Trade-off / Rationale |
| :--- | :--- | :--- | :--- |
| **Separation of Concerns** | Out-of-band PEP intercepting structured tool calls before execution. | In-prompt system instructions or secondary LLM judge. | In-prompt guardrails can be bypassed by jailbreaks; an out-of-band PEP provides deterministic enforcement regardless of model state. |
| **Human-in-the-Loop Storage** | PostgreSQL with row-level locks (`SELECT ... FOR UPDATE`) and atomic state transitions. | Redis key-value cache with TTL. | Relational database enables unified transactional audit trails, strict foreign key constraints, and relational queries for compliance reporting. |
| **Parameter Integrity** | SHA-256 hash of canonically sorted JSON arguments bound to approval ID. | Storing raw argument copies in approvals table. | Hashing prevents secret parameter reflection in approval metadata and guarantees bit-level tamper detection without bloating storage. |
| **Frontend Architecture** | Next.js 15 App Router with server-side BFF proxy and HttpOnly signed cookies. | Single-Page Application (SPA) calling FastAPI directly with browser-held API keys. | Eliminates client-side credential exposure (`NEXT_PUBLIC_` keys). Browser never holds backend API keys or database connection strings. |
| **Migration Lifecycle** | Standalone migration CLI (`scripts/migrate.py`) executed during release phase. | Auto-running `Base.metadata.create_all()` inside FastAPI lifespan startup. | Prevents DDL race conditions and deadlocks when scaling across multiple Uvicorn/container instances. |

---

## 5. Most Defensible Security Engineering Contributions

### 1. Proof of Enforcement Under Content Detector Failure
In PromptProbe's `no_detection_baseline` evaluation mode, all content detectors are completely disabled (recall drops to 0.0%). Despite 100% of adversarial injection payloads reaching the model, **unauthorized tool executions remained exactly 0**. This proves empirically that runtime security does not hinge on fragile linguistic filters.

### 2. Elimination of Concurrency Races in Approval Workflows
In sensitive workflows (e.g., financial transfers or bulk record exports), human approvals must be strictly single-use. We implemented row-level locking (`SELECT ... FOR UPDATE`) in `ApprovalService.consume()` and verified with concurrent threads that simultaneous execution attempts yield exactly 1 success and $N-1$ deterministic `DENY_APPROVAL_ALREADY_CONSUMED` rejections.

### 3. Redaction Boundaries and Zero-Leak Exception Handling
Pydantic validation errors can inadvertently echo confidential request arguments (e.g., API keys, customer SSNs) back in HTTP 422 responses. SentinelLLM implements custom error sanitizers (`_sanitize_validation_error`) and deep recursive dictionary scrubbers in audit loggers, eliminating reflection vulnerabilities.

### 4. Non-Root Multi-Stage Container Packaging
The backend Docker image uses multi-stage builds separating wheel compilation from the minimal runtime image. The application executes as an unprivileged system user (`UID 10001: sentinel`), forwards OS process signals via `exec`, and exposes standardized `/healthz` and `/readyz` probes.

---

## 6. Quantitative Results & Evaluation Scope

### PromptProbe Starter Benchmark Suite (`starter_adversarial_v1.json`)
- **Dataset Size:** 23 single-case synthetic test cases (16 content scanning cases, 7 tool authorization cases).
- **Random Seed:** Deterministically pinned to `42`.
- **Probabilistic Detector Accuracy:** **93.75%** (15 / 16 cases).
- **Detector Precision:** **1.0000** (7 TP / 7 TP + 0 FP, 0.0% false alarm rate).
- **Detector Recall:** **0.8750** (7 TP / 7 TP + 1 FN).
- **Enforcement Accuracy:** **1.0000** (100% across 7 action cases: 2 permitted, 4 denied, 1 held for approval).
- **Unauthorized Executions:** **0 (Target: 0)**.
- **Overall Specification Pass:** **22 / 23 cases (95.7%)**.

### Multi-Step Scenario Evaluations (`starter_scenarios_v1.json`)
- **Scenario Count:** 10 end-to-end multi-step scenarios (28 total steps).
- **Scenario Pass Rate:** **100.0%** (10 / 10 passed).
- **Unauthorized Executions in Scenarios:** **0**.
- **Actions Correctly Blocked:** 7 actions.
- **Actions Held for Approval:** 2 actions.
- **Provenance Boundary Violations:** 0.

### Code Quality & Test Coverage
- **Source Files Checked:** 96 files under `src/`, `promptprobe/`, `tests/`, and `scripts/`.
- **Type Safety:** 100% strict Mypy compliance (`--strict`).
- **Code Style:** 100% Ruff lint and format compliance.
- **Automated Tests:** 268 tests (264 unit/security/smoke tests + 4 real PostgreSQL integration tests).
- **Branch Test Coverage:** **91%+** across all backend modules.
- **Frontend Security Tests:** 16 tests covering CSRF, path traversal, bundle secret leaks, and role authorization.

---

## 7. Honest Limitations & Future Work

When presenting this project, transparently discuss these boundaries:

1. **Synthetic vs. Real-World Attack Diversity:**
   - *Current State:* Evaluated against 23 synthetic test cases and 10 scenarios.
   - *Limitation:* Synthetic markers do not encompass all multilingual, multi-turn, or adaptive semantic evasions.
   - *Future Work:* Expand dataset with community benchmarks (e.g., BIU, AdvGLUE, In-The-Wild jailbreaks).

2. **Regex Detector Fragility (`INJ-DIR-002`):**
   - *Current State:* Heuristic regex detectors achieved 87.5% recall, missing case `INJ-DIR-002` ("Disregard prior constraints...").
   - *Limitation:* String matching cannot understand semantic equivalence.
   - *Future Work:* Integrate lightweight local ONNX transformer classifiers (e.g. DeBERTa v3 fine-tuned for injection detection) as optional pluggable detectors.

3. **Live LLM Cost & Rate Limit Management:**
   - *Current State:* Live LLM provider adapters (OpenAI, Gemini) are implemented with strict token budgeting ($0.20 budget cap), but evaluations in CI rely on `FakeLLMAdapter` to avoid unmetered external cloud costs.
   - *Future Work:* Conduct recurring automated evaluations against real frontier models on fixed release cycles.

---

## 8. Suggested Demonstration Flow for Technical Interviews

Run through this 5-minute live terminal walkthrough:

```bash
# 1. Show code quality and test discipline (takes ~4s)
make check

# 2. Run the deterministic 6-stage security walkthrough
make demo
```

**Walkthrough Talking Points:**
1. **Stage 1 (Direct Injection):** Point out gateway interception; prompt is dropped before LLM inference.
2. **Stage 2 (Indirect RAG Injection):** Explain how retrieved documents are tagged `UNTRUSTED_CONTEXT` and quarantined.
3. **Stage 3 (Unauthorized Tool Call):** Show the model attempting an export; PEP denies execution based on host identity.
4. **Stage 4 (Approval Suspension):** Show high-impact action transitioning to `PENDING_APPROVAL`.
5. **Stage 5 (Supervisor Approval):** Show supervisor approving and atomic single-use consumption.
6. **Stage 6 (Replay & Tampering Defense):** Show parameter tampering blocked by argument hash mismatch, and token reuse blocked as `ALREADY_CONSUMED`.

```bash
# 3. Show empirical benchmark with triage transparency
python -m promptprobe run --include-scenarios
```
Point out the 22/23 result: explain why `INJ-DIR-002` was transparently kept as a false negative rather than overfitting regexes, and highlight the **0 Unauthorized Executions** invariant.
