"""Real PostgreSQL integration test suite for SentinelLLM database persistence.

Requirements:
- Opt-in via POSTGRES_TEST_URL environment variable.
- Exercises real PostgreSQL: Alembic schema migrations, row-level locking (SELECT ... FOR UPDATE),
  concurrent approval double-spending defense, transaction rollback, and rate limiting.
- When POSTGRES_TEST_URL is not set, tests skip cleanly with an explicit explanation.
"""

import concurrent.futures
import contextlib
import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from sentinelllm.api.rate_limiter import SqlRateLimiter
from sentinelllm.approvals.models import (
    compute_argument_hash,
)
from sentinelllm.approvals.service import ApprovalService
from sentinelllm.db.approval_store import SqlApprovalStore
from sentinelllm.db.models import ApprovalRequestModel
from sentinelllm.policy.engine import REASON_DENY_APPROVAL_ALREADY_CONSUMED
from sentinelllm.policy.principal import AuthenticatedPrincipal

POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL") or os.getenv("SENTINELLLM_POSTGRES_TEST_URL")
CI_ENFORCE_POSTGRES = os.getenv("CI_ENFORCE_POSTGRES", "false").lower() in ("true", "1", "yes")

if CI_ENFORCE_POSTGRES and not POSTGRES_TEST_URL:
    raise RuntimeError(
        "CI_ENFORCE_POSTGRES is enabled but POSTGRES_TEST_URL is not configured. "
        "The PostgreSQL integration test suite cannot silently skip in CI."
    )

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason=(
        "POSTGRES_TEST_URL environment variable is not configured. "
        "A real PostgreSQL instance is required for this integration suite. "
        "Configured automatically in CI via postgres:16 service container."
    ),
)


@pytest.fixture(scope="module")
def postgres_engine() -> Generator[Any, None, None]:
    """Provide a SQLAlchemy Engine connected to the real PostgreSQL test database."""
    assert POSTGRES_TEST_URL is not None
    url = POSTGRES_TEST_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    engine = create_engine(url, pool_size=15, max_overflow=5, pool_pre_ping=True)

    # Pre-flight check
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    # Execute Alembic migrations up to head
    project_root = Path(__file__).resolve().parent.parent.parent
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(alembic_cfg, "head")

    yield engine

    # Clean up / rollback migrations after suite completes
    with contextlib.suppress(Exception):
        command.downgrade(alembic_cfg, "base")
    engine.dispose()


@pytest.fixture
def session_factory(postgres_engine: Any) -> sessionmaker[Session]:
    """Provide a thread-safe sessionmaker bound to the PostgreSQL test engine."""
    return sessionmaker(bind=postgres_engine, autoflush=False, expire_on_commit=False)


@pytest.mark.integration
def test_postgres_schema_inspection(postgres_engine: Any) -> None:
    """Verify that Alembic migrations created all expected tables and columns on PostgreSQL."""
    inspector = inspect(postgres_engine)
    tables = inspector.get_table_names()

    assert "approval_requests" in tables
    assert "audit_events" in tables
    assert "policy_versions" in tables
    assert "benchmark_runs" in tables
    assert "rate_limit_buckets" in tables
    assert "alembic_version" in tables

    # Check approval_requests indexes
    indexes = {idx["name"] for idx in inspector.get_indexes("approval_requests")}
    assert "ix_approval_requests_status" in indexes
    assert "ix_approval_requests_principal_id" in indexes


@pytest.mark.integration
def test_postgres_concurrent_approval_consumption_row_level_locking(
    session_factory: sessionmaker[Session],
) -> None:
    """Verify that 10 concurrent database connections on PostgreSQL cannot double-spend an approval.

    Security Invariant (RSK-01):
    PostgreSQL row-level locking (SELECT ... FOR UPDATE) guarantees that exactly 1 worker
    successfully consumes the token, while all 9 concurrent attempts receive
    REASON_DENY_APPROVAL_ALREADY_CONSUMED.
    """
    approval_store = SqlApprovalStore(session_factory)
    service = ApprovalService(store=approval_store)

    analyst = AuthenticatedPrincipal(
        principal_id="pg_analyst",
        roles=frozenset({"analyst"}),
        permissions=frozenset({"records:export"}),
    )
    supervisor = AuthenticatedPrincipal(
        principal_id="pg_supervisor",
        roles=frozenset({"supervisor"}),
        permissions=frozenset({"approvals:manage"}),
    )

    arg_hash = compute_argument_hash({"format": "csv"})

    # 1. Create a pending approval
    rec, _ = service.create_approval(
        request_id="req_pg_concurrency",
        principal_id=analyst.principal_id,
        tool_name="export_customer_records",
        action_name="tools:execute:export_customer_records",
        argument_hash=arg_hash,
        policy_version="1.0.0",
        ttl_seconds=300,
    )

    # 2. Supervisor approves the request
    service.approve(rec.approval_id, approver=supervisor)

    # 3. Launch 10 concurrent threads attempting to consume the single approval token
    consumption_results: list[tuple[bool, str, Any]] = []
    errors: list[Exception] = []

    def consume_worker() -> None:
        try:
            res = service.consume(
                approval_id=rec.approval_id,
                principal=analyst,
                tool_name="export_customer_records",
                action_name="tools:execute:export_customer_records",
                argument_hash=arg_hash,
                policy_version="1.0.0",
            )
            consumption_results.append(res)
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(consume_worker) for _ in range(10)]
        concurrent.futures.wait(futures)

    assert len(errors) == 0, f"Concurrent workers encountered unexpected exceptions: {errors}"
    assert len(consumption_results) == 10

    # Exactly 1 success
    successes = [r for r in consumption_results if r[0] is True]
    assert len(successes) == 1, f"Expected exactly 1 successful consumption, got {len(successes)}"

    # Exactly 9 rejections with already consumed reason code
    rejections = [r for r in consumption_results if r[0] is False]
    assert len(rejections) == 9
    for _success, reason, _event in rejections:
        assert reason == REASON_DENY_APPROVAL_ALREADY_CONSUMED


@pytest.mark.integration
def test_postgres_transaction_rollback_on_integrity_error(
    session_factory: sessionmaker[Session],
) -> None:
    """Verify that primary key conflict on PostgreSQL rolls back transaction cleanly."""
    duplicate_id = f"pg_dup_id_{int(datetime.now(UTC).timestamp())}"

    with session_factory() as session:
        model1 = ApprovalRequestModel(
            approval_id=duplicate_id,
            request_id="req_dup_1",
            principal_id="user_1",
            tool_name="test_tool",
            action_name="tools:execute:test_tool",
            argument_hash="hash_1",
            policy_version="1.0.0",
            status="PENDING",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        session.add(model1)
        session.commit()

    # Second insertion with same approval_id must fail with IntegrityError and rollback
    with session_factory() as session:
        model2 = ApprovalRequestModel(
            approval_id=duplicate_id,
            request_id="req_dup_2",
            principal_id="user_2",
            tool_name="test_tool",
            action_name="tools:execute:test_tool",
            argument_hash="hash_2",
            policy_version="1.0.0",
            status="PENDING",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        session.add(model2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    # Verify original record is unharmed
    with session_factory() as session:
        stored = session.query(ApprovalRequestModel).filter_by(approval_id=duplicate_id).one()
        assert stored.request_id == "req_dup_1"


@pytest.mark.integration
def test_postgres_rate_limiter_concurrency(
    session_factory: sessionmaker[Session],
) -> None:
    """Verify that SqlRateLimiter handles concurrent worker inserts on PostgreSQL."""
    limiter = SqlRateLimiter(session_factory=session_factory)
    key = f"pg_rate_test_{int(datetime.now(UTC).timestamp())}"

    results: list[tuple[bool, int, float]] = []
    errors: list[Exception] = []

    def rate_worker() -> None:
        try:
            res = limiter.check_rate_limit(key=key, max_requests=25, window_seconds=60)
            results.append(res)
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(rate_worker) for _ in range(10)]
        concurrent.futures.wait(futures)

    assert len(errors) == 0, f"Rate limiter concurrency errors on PostgreSQL: {errors}"
    assert len(results) == 10
    assert all(r[0] is True for r in results)
