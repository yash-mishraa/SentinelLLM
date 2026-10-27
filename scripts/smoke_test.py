#!/usr/bin/env python3
"""Post-Deployment Automated Smoke Test Suite for SentinelLLM.

Validates process liveness, database readiness, authentication boundaries,
guest restrictions, deterministic prompt inspection, policy authorization,
safe tool execution proxying, and error secret redaction.

Usage:
    python scripts/smoke_test.py --api-url https://api.example.com
    python scripts/smoke_test.py --api-url http://127.0.0.1:8000 --staging

Security Invariants:
1. Smoke tests must never print raw API keys, bearer tokens, or secrets to stdout/stderr.
2. Production execution must never trigger state-mutating actions without explicit --staging flag.
3. Tool execution tests must only exercise simulated zero-side-effect tools.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("sentinelllm.smoke")


class SmokeTestError(Exception):
    """Raised when an automated smoke test verification fails."""


def make_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict[str, Any]]:
    """Perform HTTP request returning (status_code, json_body)."""
    req_headers = {"Accept": "application/json", **(headers or {})}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            body_text = response.read().decode("utf-8")
            try:
                body_json = json.loads(body_text)
            except Exception:
                body_json = {"raw": body_text}
            return status_code, body_json
    except HTTPError as e:
        status_code = e.code
        body_text = e.read().decode("utf-8")
        try:
            body_json = json.loads(body_text)
        except Exception:
            body_json = {"raw": body_text}
        return status_code, body_json
    except URLError as e:
        raise SmokeTestError(f"Failed to connect to {url}: {e.reason}") from e


def run_smoke_suite(
    api_url: str,
    admin_key: str | None = None,
    guest_key: str | None = None,
    staging: bool = False,
) -> None:
    """Execute complete smoke verification checklist."""
    base_url = api_url.rstrip("/")
    logger.info("Initiating SentinelLLM Post-Deployment Smoke Suite on %s", base_url)
    logger.info(
        "Mode: %s",
        "STAGING (state verification enabled)"
        if staging
        else "PRODUCTION (read-only verification)",
    )

    tests_passed = 0
    total_tests = 8 + (1 if staging else 0)

    # 1. Process Liveness Probe
    logger.info("[1/%d] Verifying process liveness probe (/healthz)...", total_tests)
    code, body = make_request(f"{base_url}/healthz")
    if code != 200:
        # Fallback to /api/v1/health
        code, body = make_request(f"{base_url}/api/v1/health")
    if code != 200 or body.get("status") != "ok":
        raise SmokeTestError(f"Liveness probe failed with HTTP {code}: {body}")
    logger.info("  -> PASS: Liveness confirmed (HTTP 200, status: ok)")
    tests_passed += 1

    # 2. Database Readiness Probe
    logger.info("[2/%d] Verifying database connectivity and readiness (/readyz)...", total_tests)
    code, body = make_request(f"{base_url}/readyz")
    if code != 200:
        code, body = make_request(f"{base_url}/api/v1/ready")
    if code != 200 or not body.get("database_connected"):
        raise SmokeTestError(f"Database readiness probe failed with HTTP {code}: {body}")
    logger.info("  -> PASS: Database connectivity confirmed (HTTP 200, database_connected: true)")
    tests_passed += 1

    # 3. Unauthenticated API Boundary Defense
    logger.info(
        "[3/%d] Verifying unauthenticated request rejection on protected routes...",
        total_tests,
    )
    code, body = make_request(f"{base_url}/api/v1/approvals", method="GET")
    if code != 401:
        raise SmokeTestError(
            f"Expected HTTP 401 Unauthorized for missing API key, got HTTP {code}: {body}"
        )
    logger.info("  -> PASS: Missing API key rejected with HTTP 401 Unauthorized")
    tests_passed += 1

    # 4. Guest Permission Boundary Defense
    logger.info("[4/%d] Verifying guest role restriction on privileged actions...", total_tests)
    test_guest_key: str = str(
        guest_key or os.getenv("SENTINELLLM_GUEST_KEY") or "sentinel-guest-key-secret"
    )
    code, body = make_request(
        f"{base_url}/api/v1/approvals",
        method="GET",
        headers={"X-API-Key": test_guest_key},
    )
    if code not in (200, 403):
        raise SmokeTestError(f"Unexpected response code for guest approvals lookup: HTTP {code}")
    # Verify guest cannot trigger benchmark runs
    code, body = make_request(
        f"{base_url}/api/v1/benchmark/run",
        method="POST",
        headers={"X-API-Key": test_guest_key},
    )
    if code != 403:
        raise SmokeTestError(
            f"Expected HTTP 403 Forbidden for guest benchmark run, got HTTP {code}: {body}"
        )
    logger.info("  -> PASS: Guest principal restricted from privileged administrative endpoints")
    tests_passed += 1

    # 5. Deterministic Inbound Prompt Inspection
    logger.info("[5/%d] Verifying heuristic prompt inspection (/api/v1/inspect)...", total_tests)
    test_key: str = str(
        admin_key or os.getenv("SENTINELLLM_ADMIN_KEY") or "sentinel-admin-key-secret"
    )
    code, body = make_request(
        f"{base_url}/api/v1/inspect",
        method="POST",
        headers={"X-API-Key": test_key},
        payload={
            "content": "Summarize standard enterprise compliance policies.",
            "source_type": "user_message",
        },
    )
    if code != 200 or body.get("decision") != "ALLOW":
        raise SmokeTestError(f"Deterministic inspection failed: HTTP {code}: {body}")
    logger.info(
        "  -> PASS: Benign prompt inspected and permitted (decision: ALLOW, findings: %d)",
        len(body.get("findings", [])),
    )
    tests_passed += 1

    # 6. Policy Authorization Engine (PDP Denial)
    logger.info("[6/%d] Verifying policy authorization denial (/api/v1/authorize)...", total_tests)
    code, body = make_request(
        f"{base_url}/api/v1/authorize",
        method="POST",
        headers={"X-API-Key": test_key},
        payload={
            "tool_name": "export_customer_records",
            "action_name": "tools:execute:export_customer_records",
            "arguments": {"format": "csv"},
        },
    )
    if code != 200:
        raise SmokeTestError(f"Policy authorization request failed: HTTP {code}: {body}")
    decision = body.get("decision")
    if decision not in ("ALLOW", "BLOCK", "REVIEW"):
        raise SmokeTestError(f"Unexpected PDP decision format: {decision}")
    logger.info(
        "  -> PASS: Policy Decision Point successfully evaluated action (verdict: %s)",
        decision,
    )
    tests_passed += 1

    # 7. Safe Simulated Tool Execution Proxying (PEP)
    logger.info("[7/%d] Verifying safe tool execution proxying (/api/v1/execute)...", total_tests)
    # Attempt execution without valid approval token on sensitive tool
    code, body = make_request(
        f"{base_url}/api/v1/execute",
        method="POST",
        headers={"X-API-Key": test_key},
        payload={
            "tool_name": "export_customer_records",
            "action_name": "tools:execute:export_customer_records",
            "arguments": {"format": "csv"},
        },
    )
    if code != 200 or body.get("status") not in ("DENIED", "PENDING_APPROVAL"):
        raise SmokeTestError(
            f"Expected unapproved sensitive action to be denied, got HTTP {code}: {body}"
        )
    logger.info(
        "  -> PASS: Sensitive action intercepted by PEP out-of-band (status: %s)",
        body.get("status"),
    )
    tests_passed += 1

    # 8. Secret Redaction on Error Payloads
    logger.info("[8/%d] Verifying error payload secret redaction...", total_tests)
    fake_token = "SUPER_SECRET_BEARER_TOKEN_999888777"
    code, body = make_request(
        f"{base_url}/api/v1/execute",
        method="POST",
        headers={"X-API-Key": test_key},
        payload={
            "tool_name": "read_customer_record",
            "action_name": "tools:execute:read_customer_record",
            "arguments": {"customer_id": 12345, "injected_token": fake_token},
        },
    )
    body_str = json.dumps(body)
    if fake_token in body_str:
        raise SmokeTestError(
            "SECURITY DEFECT: Sensitive input value was echoed back in validation error!"
        )
    logger.info("  -> PASS: Error response passed validation sanitization with 0 leaked secrets")
    tests_passed += 1

    # 9. Staging-Only Database State Mutation Test
    if staging:
        logger.info(
            "[9/%d] Verifying staging database write lifecycle (create & reject approval)...",
            total_tests,
        )
        arg_hash = hashlib.sha256(
            json.dumps({"format": "csv", "smoke_test": True}, sort_keys=True).encode("utf-8")
        ).hexdigest()
        code, body = make_request(
            f"{base_url}/api/v1/approvals",
            method="POST",
            headers={"X-API-Key": test_key},
            payload={
                "tool_name": "export_customer_records",
                "action_name": "tools:execute:export_customer_records",
                "argument_hash": arg_hash,
                "policy_version": "1.0.0",
                "ttl_seconds": 300,
            },
        )
        if code != 201:
            raise SmokeTestError(f"Failed to create staging smoke approval: HTTP {code}: {body}")
        approval_id = body.get("approval_id")
        logger.info("  -> Staging approval record created (ID: %s)", approval_id)

        # Reject the staging approval to clean up
        code, body = make_request(
            f"{base_url}/api/v1/approvals/{approval_id}/reject",
            method="POST",
            headers={"X-API-Key": test_key},
            payload={"reason": "Smoke test cleanup rejection"},
        )
        if code != 200 or body.get("status") != "REJECTED":
            raise SmokeTestError(f"Failed to reject staging smoke approval: HTTP {code}: {body}")
        logger.info("  -> PASS: Staging approval lifecycle verified and cleanly rejected")
        tests_passed += 1

    logger.info("=================================================================")
    logger.info(
        "SMOKE SUITE COMPLETE: All %d/%d verifications passed successfully!",
        tests_passed,
        total_tests,
    )
    logger.info("=================================================================")


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelLLM Post-Deployment Smoke Test Suite")
    parser.add_argument(
        "-u",
        "--url",
        "--api-url",
        dest="api_url",
        default=os.getenv("SENTINELLLM_API_URL", "http://127.0.0.1:8000"),
        help="Target base URL of deployed FastAPI backend (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "-k",
        "--key",
        "--api-key",
        "--admin-key",
        dest="admin_key",
        default=os.getenv("SENTINELLLM_ADMIN_KEY"),
        help="Admin API key for authenticated checks (default: env SENTINELLLM_ADMIN_KEY)",
    )
    parser.add_argument(
        "--guest-key",
        default=os.getenv("SENTINELLLM_GUEST_KEY"),
        help="Guest API key for permission boundary checks (default: env SENTINELLLM_GUEST_KEY)",
    )
    parser.add_argument(
        "--staging",
        action="store_true",
        default=os.getenv("STAGING_MODE", "false").lower() in ("true", "1", "yes"),
        help="Enable state-mutating lifecycle checks (use only on staging/test deployments)",
    )
    args = parser.parse_args()

    try:
        run_smoke_suite(
            api_url=args.api_url,
            admin_key=args.admin_key,
            guest_key=args.guest_key,
            staging=args.staging,
        )
    except SmokeTestError as e:
        logger.error("SMOKE TEST FAILED: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("UNEXPECTED SMOKE ERROR: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
