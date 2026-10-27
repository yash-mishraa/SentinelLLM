# SentinelLLM — Security Operations & Incident Response Runbook

This document defines security procedures, credential rotation schedules, real-time telemetry monitoring, and incident response runbooks for SentinelLLM in production.

---

## 1. Zero-Trust Security Architecture Summary

SentinelLLM enforces defense-in-depth across three decoupled security boundaries:
1. **Network & Ingress Boundary**:
   - Web frontend communicates with FastAPI exclusively via server-side Route Handlers (`/api/backend/[...path]`).
   - Browser clients never observe backend API keys or database connection strings.
   - Origin and Sec-Fetch headers are validated against CSRF attacks.
2. **Identity & Session Boundary**:
   - BFF sessions are cryptographically signed with HMAC-SHA256 (`SESSION_SECRET`).
   - Roles (`guest`, `analyst`, `supervisor`, `admin`) map to least-privilege backend API keys stored only in server-side environment variables.
3. **Execution & Policy Boundary**:
   - Model outputs are treated as completely untrusted suggestions.
   - The Policy Enforcement Point (PEP) gates all backing tool invocations out-of-band.
   - Sensitive actions require single-use, cryptographically verified approval tokens issued by an authorized supervisor.

---

## 2. Credential & Secret Rotation Procedures

### 2.1 Rotating `SESSION_SECRET` (Frontend BFF)

- **Impact**: All active browser sessions will be invalidated immediately. Users will return to the `guest` role and must re-authenticate for elevated roles. Zero downtime to backend API availability.
- **Cadence**: Every 90 days or immediately upon suspected compromise.

**Procedure:**
1. Generate a new high-entropy 256-bit hexadecimal key:
   ```bash
   openssl rand -hex 32
   ```
2. Update the secret in Vercel:
   ```bash
   vercel env add SESSION_SECRET production
   # Enter the new generated secret
   ```
3. Trigger a redeployment of the frontend:
   ```bash
   vercel redeploy
   ```
4. Confirm existing cookie signatures fail cleanly and re-issue guest sessions without 500 errors.

---

### 2.2 Rotating Role API Keys (`SENTINELLLM_ROLE_*_KEY`)

- **Impact**: Zero downtime if updated in the proper sequence. If misordered, BFF calls using the old key will receive `HTTP 401 Unauthorized`.
- **Keys**:
  - `SENTINELLLM_ROLE_GUEST_KEY`
  - `SENTINELLLM_ROLE_ANALYST_KEY`
  - `SENTINELLLM_ROLE_SUPERVISOR_KEY`
  - `SENTINELLLM_ROLE_ADMIN_KEY`

**Zero-Downtime Rotation Sequence:**
1. Generate four new cryptographically secure keys:
   ```bash
   export NEW_GUEST=$(openssl rand -hex 24)
   export NEW_ANALYST=$(openssl rand -hex 24)
   export NEW_SUPERVISOR=$(openssl rand -hex 24)
   export NEW_ADMIN=$(openssl rand -hex 24)
   ```
2. **Phase 1: Update Google Cloud Run (Backend)**
   Update the secret versions in Google Cloud Secret Manager:
   ```bash
   echo -n "$NEW_GUEST" | gcloud secrets versions add sentinel-guest-key --data-file=-
   echo -n "$NEW_ANALYST" | gcloud secrets versions add sentinel-analyst-key --data-file=-
   echo -n "$NEW_SUPERVISOR" | gcloud secrets versions add sentinel-supervisor-key --data-file=-
   echo -n "$NEW_ADMIN" | gcloud secrets versions add sentinel-admin-key --data-file=-
   ```
   Redeploy Cloud Run to load the new secret versions:
   ```bash
   gcloud run services update sentinelllm-backend --region=us-central1
   ```
3. **Phase 2: Update Vercel (Frontend BFF)**
   Update the corresponding environment variables on Vercel:
   ```bash
   vercel env add SENTINELLLM_ROLE_GUEST_KEY production
   vercel env add SENTINELLLM_ROLE_ANALYST_KEY production
   vercel env add SENTINELLLM_ROLE_SUPERVISOR_KEY production
   vercel env add SENTINELLLM_ROLE_ADMIN_KEY production
   ```
   Deploy the updated frontend:
   ```bash
   vercel --prod
   ```
4. **Phase 3: Verification**
   Verify all four roles via `/api/v1/health` and role-specific inspection/execution endpoints using `scripts/smoke_test.py`.

---

### 2.3 Rotating Database Credentials (Neon PostgreSQL)

- **Impact**: Database connection pool drain. Transient database connection errors if completed without zero-downtime dual-user rotation.
- **Cadence**: Every 180 days or upon developer offboarding.

**Procedure:**
1. Log into the **Neon Console** -> Project -> **Roles**.
2. Create a secondary database role (e.g., `sentinel_app_v2`) with matching schema permissions:
   ```sql
   CREATE ROLE sentinel_app_v2 WITH LOGIN PASSWORD 'new-secure-password';
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sentinel_app_v2;
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sentinel_app_v2;
   ```
3. Format the new connection strings for both pooled and unpooled endpoints.
4. Update `SENTINELLLM_DATABASE_URL` in Google Cloud Secret Manager and redeploy Cloud Run.
5. Verify `/ready` returns `database_connected: true`.
6. Drop or revoke the old role `sentinel_app_v1` in Neon.

---

## 3. Monitoring, Telemetry & Security Alerts

### 3.1 Primary Operational Metrics

| Metric | Target | Warning Threshold | Critical Alert | Action |
| :--- | :--- | :--- | :--- | :--- |
| **Cloud Run 5xx Rate** | 0.00% | > 0.5% for 5m | > 2.0% for 2m | Check container logs; rollback revision |
| **p95 Latency (Inspect)**| < 50ms | > 150ms | > 500ms | Inspect regex detector overhead / CPU saturation |
| **p95 Latency (Execute)**| < 120ms| > 300ms | > 1000ms | Check Neon connection pool / pgbouncer limits |
| **Neon Pool Saturation** | < 40% | > 70% | > 90% | Enable pgbouncer pooling; scale Neon compute |
| **Uncaught Exceptions** | 0 | > 5/hour | > 20/hour | Check Sentry / Cloud Logging error groups |

---

### 3.2 Security Telemetry Alerts

Monitor the structured audit trail (`AuditEvent` table) for anomalous security patterns:

```
                  ┌──────────────────────────────────────────────┐
                  │          AuditEvent Stream Monitoring        │
                  └──────────────────────┬───────────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              ▼                          ▼                          ▼
     [High BLOCK Rate]          [Repeated PEP DENIALS]     [Approval Pileup]
     Spike in injection         Unauthorized tool          Pending actions held
     findings (> 20/min)        execution attempts         without review (> 10)
              │                          │                          │
              ▼                          ▼                          ▼
     Ingress DDoS or            Compromised caller         Supervisor notification
     adversarial campaign       probing permissions        or workflow blockage
```

1. **High Inbound Quarantine Rate (`decision: "BLOCK"`)**:
   - **Trigger**: More than 20 `BLOCK` decisions within 5 minutes.
   - **Meaning**: Active adversarial attack, automated prompt fuzzer, or scanning campaign targeting the gateway.
   - **Action**: Inspect originating IP addresses in Cloud Run metrics; apply Cloud Armor or WAF rate-limiting.

2. **Repeated Tool Execution Denials (`decision: "DENIED"`)**:
   - **Trigger**: 5 or more `DENIED` decisions for a single `principal_id` within 10 minutes.
   - **Meaning**: Probable compromised API key or malicious insider attempting unauthorized capability execution.
   - **Action**: Immediately revoke the principal's API key; audit the principal's historical requests.

3. **Approval Queue Stagnation (`status: "PENDING"`)**:
   - **Trigger**: > 10 requests pending supervisor approval older than 30 minutes.
   - **Meaning**: Approver bottleneck or workflow stall.

---

## 4. Incident Response Runbooks

### 4.1 Incident Severity Matrix

- **Severity 1 (Critical)**:
  - Confirmed prompt-injection bypass leading to unauthorized external tool execution.
  - Exposure of raw customer data or database secrets.
  - Complete backend outage or database corruption in production.
- **Severity 2 (High)**:
  - Service degradation (p95 latency > 2s, error rate > 5%).
  - Database connectivity failure with read-only fallback active.
  - Misconfiguration causing legitimate users to be blocked.
- **Severity 3 (Medium)**:
  - Elevated rate of heuristic false positives on benign user prompts.
  - Delay in supervisor approval notifications.

---

### 4.2 Severity 1 Runbook: Suspected Injection Bypass or Unauthorized Tool Execution

```
[ALERT TRIGGERED] ──► [CONTAINMENT: 10 mins] ──► [FORENSICS & AUDIT] ──► [ROOT CAUSE & REMEDIATION]
                      1. Invalidate API Keys     1. Query /api/v1/audit   1. Add detector heuristic
                      2. Drain Approvals         2. Extract request_id    2. Patch PEP policy
                      3. Route to Safe Revision  3. Map affected data     3. Tag release & verify
```

#### Step 1: Immediate Containment (< 10 minutes)
1. **Revoke the Compromised Credential**:
   Rotate the role API key or revoke the offending `principal_id` immediately:
   ```bash
   # Rotate the affected role key to sever active attacker sessions
   echo -n "$(openssl rand -hex 24)" | gcloud secrets versions add sentinel-analyst-key --data-file=-
   gcloud run services update sentinelllm-backend --region=us-central1
   ```
2. **Invalidate All Pending Approvals**:
   Cancel any in-flight supervisor approval requests to prevent delayed execution:
   ```sql
   UPDATE approvals
   SET status = 'REJECTED',
       resolved_by = 'SECURITY_EMERGENCY_DRAIN',
       resolution_reason = 'Incident containment: global drain',
       updated_at = NOW()
   WHERE status = 'PENDING';
   ```
3. **Rollback to Known Good Revision**:
   If the bypass stemmed from a recent policy engine or detector update:
   ```bash
   gcloud run services update-traffic sentinelllm-backend --to-revisions=[KNOWN_SAFE_REVISION]=100 --region=us-central1
   ```

#### Step 2: Forensic Reconstruction via Audit Explorer (< 30 minutes)
1. Retrieve the complete event timeline associated with the suspect `request_id`:
   ```bash
   curl -s -X GET "https://your-backend.run.app/api/v1/audit/query?request_id=[SUSPECT_REQUEST_ID]" \
     -H "X-API-Key: $ADMIN_KEY" | jq .
   ```
2. Inspect the audit log for:
   - Inbound prompt content and detector findings emitted (`INSPECT_PROMPT`).
   - Proposed tool actions, arguments, and required permissions (`AUTHORIZE_ACTION`).
   - Supervisor approval verification records (`CREATE_APPROVAL`, `RESOLVE_APPROVAL`).
   - Actual tool execution payload and result disposition (`EXECUTE_TOOL`).
3. Confirm whether any customer data was extracted by checking the sanitized output payloads.

#### Step 3: Root Cause Analysis & Permanent Remediation
1. Reproduce the bypass payload in `tests/unit/test_detectors.py` or `tests/integration/test_policy_enforcement.py`.
2. Add a targeted heuristic pattern to `src/sentinelllm/detectors/regex_detector.py` or tighten action permissions in `src/sentinelllm/policy/engine.py`.
3. Run the full validation suite:
   ```bash
   make check
   make demo
   python -m promptprobe run --include-scenarios
   ```
4. Release a patch version (e.g., `v1.0.1`), update documentation, and publish an internal post-mortem.
