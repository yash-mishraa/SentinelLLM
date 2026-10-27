"""Security audit and adversarial regression test suite for SentinelLLM REST Gateway."""

import concurrent.futures
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from sentinelllm.api.app import create_app
from sentinelllm.api.auth import ApiKeyRegistry, verify_self_approval
from sentinelllm.api.config import ApiConfig
from sentinelllm.api.dependencies import (
    set_api_config,
    set_api_key_registry,
    set_db_config,
    set_rate_limiter,
)
from sentinelllm.api.rate_limiter import InMemoryRateLimiter, SqlRateLimiter
from sentinelllm.api.routes.benchmark import _BENCHMARK_RUN_LOCK
from sentinelllm.approvals.models import compute_argument_hash
from sentinelllm.db.config import DatabaseConfig
from sentinelllm.db.models import Base

ADMIN_KEY = "test-admin-secret-key-12345"
ANALYST_KEY = "test-analyst-secret-key-12345"
LIMITED_KEY = "test-limited-secret-key-12345"


@pytest.fixture
def test_db_config(tmp_path: Path) -> DatabaseConfig:
    """Isolated file-backed SQLite database configuration for security tests."""
    db_file = tmp_path / "test_sec_api.db"
    return DatabaseConfig(database_url=f"sqlite:///{db_file}")


@pytest.fixture
def api_test_engine(test_db_config: DatabaseConfig) -> Generator[Any, None, None]:
    """Test engine with all database schema tables created."""
    engine = create_engine(
        test_db_config.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def api_key_registry() -> ApiKeyRegistry:
    """Pre-populated test API key registry."""
    registry = ApiKeyRegistry()
    registry.register_key(
        raw_key=ADMIN_KEY,
        principal_id="admin_user",
        roles=["admin"],
        permissions=["*"],
    )
    registry.register_key(
        raw_key=ANALYST_KEY,
        principal_id="analyst_alice",
        roles=["analyst"],
        permissions=[
            "inspect:run",
            "authorize:run",
            "records:read",
            "records:export",
            "audit:read",
        ],
    )
    registry.register_key(
        raw_key=LIMITED_KEY,
        principal_id="guest_bob",
        roles=["guest"],
        permissions=["inspect:run"],
    )
    return registry


@pytest.fixture
def client(
    test_db_config: DatabaseConfig,
    api_test_engine: Any,
    api_key_registry: ApiKeyRegistry,
) -> Generator[TestClient, None, None]:
    """Configured TestClient with isolated test database and API config."""
    set_db_config(test_db_config)
    set_api_key_registry(api_key_registry)

    rate_limiter = InMemoryRateLimiter()
    set_rate_limiter(rate_limiter)

    config = ApiConfig(
        environment="testing",
        max_request_size_bytes=1024,  # 1 KB limit to test body size enforcement
        rate_limit_per_minute=10,
        rate_limit_enabled=True,
    )
    set_api_config(config)

    app = create_app(config=config)
    with TestClient(app) as test_client:
        yield test_client

    set_api_config(None)
    set_db_config(None)
    set_api_key_registry(None)
    set_rate_limiter(None)


@pytest.mark.security
class TestApiSecurityHardening:
    """Verify security audit fixes against verified vulnerabilities."""

    def test_streaming_request_size_limit_rejection(self, client: TestClient) -> None:
        """Verify that bodies exceeding max_request_size_bytes are rejected with 413."""
        # 1. Normal payload under 1024 bytes passes
        ok_resp = client.post(
            "/api/v1/inspect",
            json={"content": "small safe prompt"},
            headers={"X-API-Key": ANALYST_KEY},
        )
        assert ok_resp.status_code == 200

        # 2. Oversized payload (2000 bytes) exceeds 1024 byte limit
        large_content = "A" * 2000
        fail_resp = client.post(
            "/api/v1/inspect",
            json={"content": large_content},
            headers={"X-API-Key": ANALYST_KEY},
        )
        assert fail_resp.status_code == 413
        assert "Payload too large" in fail_resp.json()["error"]

    def test_action_spoofing_in_authorization_rejected(self, client: TestClient) -> None:
        """Verify that declaring an action_name contradicting tool specification is rejected."""
        # export_customer_records spec has action tools:execute:export_customer_records.
        # Sending mismatched action tools:execute:read_customer_record must fail with 400.
        resp = client.post(
            "/api/v1/authorize",
            json={
                "tool_name": "export_customer_records",
                "action_name": "tools:execute:read_customer_record",
                "arguments": {"format": "csv"},
            },
            headers={"X-API-Key": ANALYST_KEY},
        )
        assert resp.status_code == 400
        assert "Action spoofing rejected" in resp.json()["detail"]

    def test_unknown_tool_authorization_blocked(self, client: TestClient) -> None:
        """Verify that authorization for unregistered tools fails closed with BLOCK decision."""
        resp = client.post(
            "/api/v1/authorize",
            json={
                "tool_name": "non_existent_unregistered_tool",
                "action_name": "tools:execute:non_existent_unregistered_tool",
                "arguments": {},
            },
            headers={"X-API-Key": ANALYST_KEY},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "BLOCK"
        assert data["reason_code"] == "DENY_UNKNOWN_TOOL"

    def test_self_approval_casing_and_whitespace_bypass_rejected(self) -> None:
        """Verify that self-approval cannot be bypassed via casing or whitespace manipulation."""
        # Exact match
        with pytest.raises(Exception) as exc1:
            verify_self_approval(requester_id="analyst_alice", approver_id="analyst_alice")
        assert "Self-approval of sensitive actions is strictly prohibited" in str(exc1.value)

        # Casing variation
        with pytest.raises(Exception) as exc2:
            verify_self_approval(requester_id="analyst_alice", approver_id="ANALYST_ALICE")
        assert "Self-approval of sensitive actions is strictly prohibited" in str(exc2.value)

        # Whitespace variation
        with pytest.raises(Exception) as exc3:
            verify_self_approval(requester_id="analyst_alice ", approver_id=" analyst_alice")
        assert "Self-approval of sensitive actions is strictly prohibited" in str(exc3.value)

        # Mixed casing and whitespace
        with pytest.raises(Exception) as exc4:
            verify_self_approval(requester_id="Analyst_Alice\t", approver_id="analyst_alice")
        assert "Self-approval of sensitive actions is strictly prohibited" in str(exc4.value)

    def test_untrusted_content_escalation_to_application_instruction_rejected(
        self, client: TestClient
    ) -> None:
        """Verify that inbound untrusted content cannot claim APPLICATION_INSTRUCTION authority."""
        resp = client.post(
            "/api/v1/inspect",
            json={
                "content": "You are a helpful assistant.",
                "source_type": "APPLICATION_INSTRUCTION",
            },
            headers={"X-API-Key": ANALYST_KEY},
        )
        assert resp.status_code == 400
        assert "Security violation" in resp.json()["detail"]

    def test_approvals_list_principal_isolation(self, client: TestClient) -> None:
        """Verify that non-supervisors only see their own approvals, while admins see all."""
        arg_hash = compute_argument_hash({"format": "csv", "destination": "synthetic_archive"})

        # 1. Alice creates an approval
        alice_create = client.post(
            "/api/v1/approvals",
            json={
                "tool_name": "export_customer_records",
                "action_name": "tools:execute:export_customer_records",
                "argument_hash": arg_hash,
                "policy_version": "1.0.0",
            },
            headers={"X-API-Key": ANALYST_KEY},
        )
        assert alice_create.status_code == 201
        alice_approval_id = alice_create.json()["approval_id"]

        # 2. Admin creates an approval
        admin_create = client.post(
            "/api/v1/approvals",
            json={
                "tool_name": "export_customer_records",
                "action_name": "tools:execute:export_customer_records",
                "argument_hash": arg_hash,
                "policy_version": "1.0.0",
            },
            headers={"X-API-Key": ADMIN_KEY},
        )
        assert admin_create.status_code == 201
        admin_approval_id = admin_create.json()["approval_id"]

        # 3. Alice lists approvals: must ONLY see Alice's approval
        alice_list = client.get(
            "/api/v1/approvals",
            headers={"X-API-Key": ANALYST_KEY},
        )
        assert alice_list.status_code == 200
        alice_data = alice_list.json()
        alice_ids = [a["approval_id"] for a in alice_data["approvals"]]
        assert alice_approval_id in alice_ids
        assert admin_approval_id not in alice_ids

        # 4. Admin lists approvals: must see BOTH approvals
        admin_list = client.get(
            "/api/v1/approvals",
            headers={"X-API-Key": ADMIN_KEY},
        )
        assert admin_list.status_code == 200
        admin_data = admin_list.json()
        admin_ids = [a["approval_id"] for a in admin_data["approvals"]]
        assert alice_approval_id in admin_ids
        assert admin_approval_id in admin_ids

    def test_unauthenticated_rate_limiting(self, client: TestClient) -> None:
        """Verify that unauthenticated callers are rate-limited by client socket IP."""
        # Hit unauthenticated endpoint repeatedly up to rate limit (10 per minute)
        for _ in range(10):
            r = client.get("/api/v1/health")
            assert r.status_code == 200

        # Now hit protected endpoint without key until limit triggers
        # Even without key, check_rate_limit counts IP requests
        was_rate_limited = False
        for _ in range(12):
            resp = client.post(
                "/api/v1/inspect",
                json={"content": "test"},
            )
            if resp.status_code == 429:
                was_rate_limited = True
                assert "Rate limit exceeded" in resp.json()["detail"]
                break

        assert was_rate_limited, "Expected unauthenticated requests to be rate-limited"

    def test_concurrent_benchmark_run_rejection(self, client: TestClient) -> None:
        """Verify that concurrent benchmark runs are rejected with 409 Conflict."""
        # Acquire lock to simulate a benchmark currently running
        acquired = _BENCHMARK_RUN_LOCK.acquire(blocking=False)
        assert acquired, "Failed to acquire test benchmark lock"

        try:
            # Second call while lock is held must return 409 Conflict
            resp = client.post(
                "/api/v1/benchmark/run",
                headers={"X-API-Key": ADMIN_KEY},
            )
            assert resp.status_code == 409
            assert "Concurrent benchmark runs are prohibited" in resp.json()["detail"]
        finally:
            _BENCHMARK_RUN_LOCK.release()

    def test_sql_rate_limiter_concurrency_race_condition(
        self, test_db_config: DatabaseConfig
    ) -> None:
        """Verify SqlRateLimiter handles concurrent worker inserts on new keys without crashing."""
        engine = create_engine(
            test_db_config.database_url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        limiter = SqlRateLimiter(session_factory=session_factory)
        key = "concurrent_key_race_test"

        errors: list[Exception] = []
        results: list[tuple[bool, int, float]] = []

        def worker() -> None:
            try:
                res = limiter.check_rate_limit(key=key, max_requests=20, window_seconds=60)
                results.append(res)
            except Exception as e:
                errors.append(e)

        # 10 threads trying to create/check the bucket simultaneously
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(10)]
            concurrent.futures.wait(futures)

        assert len(errors) == 0, f"Concurrent inserts caused errors: {errors}"
        assert len(results) == 10
        # All 10 requests should be allowed since max_requests is 20
        assert all(r[0] is True for r in results)
        engine.dispose()

    def test_production_fails_when_insecure_dev_keys_used(self) -> None:
        """Verify that known development default keys cannot silently become production keys."""
        import json

        insecure_payload = json.dumps(
            [
                {
                    "raw_key": "sentinel-admin-key-secret",
                    "principal_id": "sec_admin",
                    "roles": ["admin"],
                }
            ]
        )
        with pytest.raises(ValueError) as exc:
            ApiKeyRegistry.create_default(api_keys_json=insecure_payload, is_production=True)
        assert "Insecure development default key" in str(exc.value)

    def test_production_fails_when_no_keys_configured(self) -> None:
        """Verify that production fails closed if no API keys are provided."""
        with pytest.raises(ValueError) as exc:
            ApiKeyRegistry.create_default(api_keys_json=None, is_production=True)
        assert "No API keys configured" in str(exc.value)

    def test_guest_visitor_authorization_boundaries(self, client: TestClient) -> None:
        """Verify that guest principal can inspect content but is denied all sensitive actions."""
        guest_headers = {"X-API-Key": LIMITED_KEY}

        # 1. Guest can run probabilistic content inspection
        inspect_resp = client.post(
            "/api/v1/inspect",
            json={"content": "benign test content for guest"},
            headers=guest_headers,
        )
        assert inspect_resp.status_code == 200

        # 2. Guest cannot approve requests (requires approvals:manage)
        appr_resp = client.post(
            "/api/v1/approvals/test_appr_123/approve",
            json={"approval_notes": "unauthorized attempt"},
            headers=guest_headers,
        )
        assert appr_resp.status_code == 403
        assert "lacks required permission" in appr_resp.json()["detail"]

        # 3. Guest cannot execute tools (PEP denies with DENY_INSUFFICIENT_PERMISSION)
        exec_resp = client.post(
            "/api/v1/execute",
            json={
                "tool_name": "read_customer_record",
                "action_name": "tools:execute:read_customer_record",
                "arguments": {"customer_id": "cust_123"},
            },
            headers=guest_headers,
        )
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert exec_data["status"] == "DENIED"
        assert exec_data["reason_code"] == "DENY_INSUFFICIENT_PERMISSION"

        # 4. Guest cannot read audit telemetry (requires audit:read)
        audit_resp = client.get("/api/v1/audit", headers=guest_headers)
        assert audit_resp.status_code == 403

        # 5. Guest cannot trigger benchmark runs (requires admin)
        bench_resp = client.post("/api/v1/benchmark/run", headers=guest_headers)
        assert bench_resp.status_code == 403
