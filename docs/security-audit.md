# SentinelLLM Security Audit & Adversarial Review Report

> **Audit Date:** 2026-10-26  
> **Target Version:** SentinelLLM v0.1.0.dev0  
> **Status:** Completed & Remediated  
> **Audit Type:** Independent Codebase Review, Trust-Boundary Audit, and Adversarial Concurrency Testing  

---

## 1. Executive Summary

An adversarial security review of SentinelLLM was conducted focusing on trust-boundary integrity, policy enforcement correctness, approval lifecycle concurrency, information disclosure, and anti-spoofing guarantees.

Five findings were identified, analyzed, and remediated:
- **1 Critical-Severity Finding:** TOCTOU race condition enabling approval replay and double-spending under concurrent requests.
- **2 High-Severity Findings:** Information leakage of secrets in PEP validation errors; Policy Decision Point failing to enforce high-risk containment for non-injection high-severity findings.
- **2 Medium-Severity Findings:** Ingestion deserialization gap allowing spoofed principals or instructions in unvalidated contexts; AuditEvent disallowed key gap and missing recursive metadata sanitization.

All critical and high findings have been resolved with atomic concurrency synchronization, recursive key sanitization, explicit gateway validation, and broadened policy containment. Comprehensive adversarial regression tests have been added to the suite.

---

## 2. Audit Scope & Methodology

### 2.1 Audited Components
1. **Contracts & Provenance:** `contracts/provenance.py`, `contracts/messages.py`, `contracts/context.py`, `contracts/decision.py`, `contracts/audit.py`.
2. **Lifecycle & Detectors:** `orchestrator.py`, `detectors/registry.py`, `detectors/injection.py`, `detectors/extraction.py`, `detectors/canary.py`.
3. **Policy & Enforcement (PDP/PEP):** `policy/principal.py`, `policy/models.py`, `policy/engine.py`, `tools/pep.py`, `tools/registry.py`, `tools/simulated.py`.
4. **Approval Lifecycle:** `approvals/models.py`, `approvals/store.py`, `approvals/service.py`.
5. **PromptProbe Companion Harness:** `promptprobe/runner.py`, `promptprobe/scenario_runner.py`, `promptprobe/cli.py`, `promptprobe/baselines.py`.

### 2.2 Review Methodology
- **Static Code Review:** Systematic tracing of untrusted inputs from gateway ingestion to tool execution.
- **Adversarial Boundary Analysis:** Testing deserialization bypasses, casing anomalies, metadata key collisions, and role spoofing.
- **Concurrency Stress Testing:** Barrier-synchronized multi-threaded execution to expose Time-of-Check to Time-of-Use (TOCTOU) windows during approval consumption.
- **Privacy & Leakage Inspection:** Inspecting exception messages and audit metadata payloads for credential and secret leakage.

---

## 3. Findings & Remediations

### Finding 1: TOCTOU Concurrency Race Condition in Approval Consumption
- **Severity:** **CRITICAL**
- **Affected Components:** `sentinelllm.approvals.service.ApprovalService`, `sentinelllm.approvals.store.InMemoryApprovalStore`
- **Vulnerability Description:**  
  `ApprovalService.consume()` performed a non-atomic `get() -> validate -> save()` workflow without thread synchronization. Under concurrent load, multiple threads could read `status == ApprovalStatus.APPROVED` before any thread updated the state to `ApprovalStatus.CONSUMED`.
- **Exploit Scenario:**  
  An attacker issuing concurrent requests using a single approved `approval_id` could execute a sensitive action multiple times (replay / double-spending attack).
- **Remediation:**  
  Implemented `threading.RLock()` in `ApprovalService` protecting `create_approval`, `approve`, `reject`, and `consume`. Added `RLock()` synchronization to `InMemoryApprovalStore`. State transitions are now strictly atomic.
- **Regression Test:** `tests/unit/test_security_audit.py::test_concurrent_approval_consumption_is_strictly_atomic` (10 concurrent threads with simulated latency; exactly 1 succeeds, 9 fail with `DENY_APPROVAL_ALREADY_CONSUMED`).

---

### Finding 2: Information Disclosure of Secrets in PEP Validation Error Messages
- **Severity:** **HIGH**
- **Affected Components:** `sentinelllm.tools.pep.PolicyEnforcementPoint.invoke`
- **Vulnerability Description:**  
  When tool arguments failed Pydantic schema validation, the PEP formatted the error using `err.errors()`. In Pydantic v2, `err.errors()` contains an `'input'` dictionary echoing the raw input value. If a caller supplied extra forbidden fields or invalid values containing passwords, API tokens, or secrets, the raw secret value was directly embedded in `ToolExecutionResult.error_message`.
- **Exploit Scenario:**  
  An attacker or caller passing credentials in malformed arguments received raw secrets reflected back in error responses or logs.
- **Remediation:**  
  Implemented `_sanitize_validation_error()` in `PolicyEnforcementPoint`, extracting only field locations (`loc`), error messages (`msg`), and validation types (`type`) while strictly omitting raw `input` values and extra context.
- **Regression Test:** `tests/unit/test_security_audit.py::test_pep_error_message_sanitizes_raw_arguments_and_secrets`.

---

### Finding 3: Policy Decision Point Failed to Enforce High-Risk Containment on Non-Injection Findings
- **Severity:** **HIGH**
- **Affected Components:** `sentinelllm.policy.engine.PolicyDecisionPoint.evaluate`
- **Vulnerability Description:**  
  In Step 4 of policy evaluation, `PDP.evaluate()` filtered findings with `f.severity == Severity.HIGH and f.category == "prompt_injection"`. High-severity findings emitted by other detectors—such as `InstructionExtractionDetector` (`category="instruction_extraction"`)—were ignored. Consequently, requests with high-severity extraction probes that matched an `ALLOW` rule were permitted to execute.
- **Exploit Scenario:**  
  An adversary combining a system prompt extraction probe with a permitted tool call bypassed policy containment because the detector finding was categorized as extraction rather than injection.
- **Remediation:**  
  Broadened Step 4 to evaluate any `Severity.HIGH` finding (`f.severity == Severity.HIGH`) rather than restricting to `prompt_injection`.
- **Regression Test:** `tests/unit/test_security_audit.py::test_pdp_enforces_high_risk_containment_on_instruction_extraction`.

---

### Finding 4: Absence of Untrusted Context Ingestion Gateway Sanitizer
- **Severity:** **MEDIUM**
- **Affected Components:** `sentinelllm.contracts.context.RequestContext`
- **Vulnerability Description:**  
  While `parse_untrusted_content()` existed for individual messages, `RequestContext` lacked a corresponding safe parser for raw serialized dictionaries or JSON. Deserializing an untrusted context directly via `RequestContext.model_validate()` allowed callers to inject `ApplicationInstruction` into `items` and assert `AuthenticatedPrincipal` with arbitrary roles and permissions.
- **Exploit Scenario:**  
  An application endpoint accepting raw JSON payloads and deserializing them into `RequestContext` could be tricked into treating untrusted content as trusted application directives or verified administrative principals.
- **Remediation:**  
  Implemented `parse_untrusted_context(payload)` in `contracts/context.py`. It strictly parses all items through `parse_untrusted_content()` and rejects any caller-supplied authenticated principal claiming `is_authenticated=True` or roles/permissions.
- **Regression Test:** `tests/unit/test_security_audit.py::test_parse_untrusted_context_rejects_spoofed_principal` and `test_parse_untrusted_context_rejects_application_instruction_injection`.

---

### Finding 5: Disallowed Audit Key Regex Gap and Missing Recursive Sanitization
- **Severity:** **MEDIUM**
- **Affected Components:** `sentinelllm.contracts.audit.AuditEvent._reject_raw_content_in_audit_metadata`
- **Vulnerability Description:**  
  `_DISALLOWED_AUDIT_KEYS` omitted standard authentication tokens such as `token`, `auth`, `authorization`, `private_key`, `credential`. Additionally, the validator only inspected top-level dictionary keys, allowing sensitive credentials to be placed in nested metadata structures (e.g. `{"config": {"password": "..."}}`).
- **Exploit Scenario:**  
  Telemetry pipelines emitting audit records could inadvertently log sensitive credentials if passed under `auth_token` or within nested dictionaries.
- **Remediation:**  
  Expanded `_DISALLOWED_AUDIT_KEYS` to include `token`, `auth`, `authorization`, `private_key`, `credential`. Implemented recursive traversal (`_scan_keys_recursively()`) inspecting nested dictionaries, lists, and tuples.
- **Regression Test:** `tests/unit/test_security_audit.py::test_audit_event_recursively_rejects_nested_sensitive_keys`.

---

## 4. Summary of Verification & Regression Tests

| Category | Test Function | Purpose / Invariant Verified |
| :--- | :--- | :--- |
| **Concurrency** | `test_concurrent_approval_consumption_is_strictly_atomic` | Concurrency race condition; exactly 1 of 10 threads consumes approval. |
| **Privacy** | `test_pep_error_message_sanitizes_raw_arguments_and_secrets` | Validation errors never echo raw argument values or sensitive tokens. |
| **Policy** | `test_pdp_enforces_high_risk_containment_on_instruction_extraction` | Non-injection high-severity findings correctly trigger policy containment. |
| **Trust Boundary** | `test_parse_untrusted_context_rejects_spoofed_principal` | Untrusted context cannot supply authenticated principal. |
| **Trust Boundary** | `test_parse_untrusted_context_rejects_spoofed_roles_and_permissions` | Untrusted context cannot assert roles or permissions. |
| **Trust Boundary** | `test_parse_untrusted_context_rejects_application_instruction_injection` | Untrusted context cannot inject ApplicationInstruction. |
| **Trust Boundary** | `test_parse_untrusted_context_valid_inbound_parses_safely` | Valid untrusted payloads parse with None principal and untrusted provenance. |
| **Audit Privacy** | `test_audit_event_recursively_rejects_nested_sensitive_keys` | Rejects top-level and nested credential keys (`auth_token`, `password`, `private_key`). |
| **Approval Integrity** | `test_policy_version_mismatch_prevents_approval_consumption` | Policy version change causes deterministic rejection (`DENY_APPROVAL_POLICY_MISMATCH`). |
| **Approval Integrity** | `test_tampered_arguments_prevent_approval_consumption` | Modified arguments cause deterministic rejection (`DENY_APPROVAL_ARGUMENTS_MISMATCH`). |
| **Approval Integrity** | `test_critical_canary_leak_unconditionally_halts_prior_approval` | Critical canary findings unconditionally block execution even if previously approved. |

---

## 5. Unresolved Issues & Lower-Priority Observations

1. **Process-Local In-Memory Approval Store:**  
   `InMemoryApprovalStore` uses process-local threading locks (`RLock`). In multi-process or distributed cluster deployments (e.g. multiple Gunicorn/Uvicorn workers, Kubernetes replicas), an external distributed atomic store (e.g. Redis with atomic Lua scripts or PostgreSQL with row-level locks) must be used to maintain cross-instance atomicity.
2. **Regex Heuristic Brittleness:**  
   Heuristic regex pattern detectors (`InjectionPatternDetector`, `InstructionExtractionDetector`) are inherently sensitive to paraphrasing, evasion, and multilingual obfuscation. As demonstrated in PromptProbe case `INJ-DIR-002`, pattern heuristics provide defense-in-depth but cannot replace semantic classifiers or action-level authorization boundaries.

---

## 6. Residual Risk Assessment

- **Action-Level Security:** Highly robust. Tool execution is decoupled from model outputs and strictly mediated by PEP policy rules, permission checks, and argument validation.
- **Approval Replay:** Concurrency race conditions have been eliminated for process-local execution.
- **Content Trust Boundaries:** Untrusted inputs cannot elevate provenance or spoof principal identities via supported ingestion gateways.
- **Residual Risk:** Complex semantic jailbreaks that evade regex patterns remain possible at the content layer; the primary safeguard remains PEP fail-closed action containment and least privilege.
