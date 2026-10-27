"""Unit and integration tests for SentinelLLM database persistence and concurrency."""

import os
import threading
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sentinelllm.approvals.models import ApprovalRequest, ApprovalStatus, compute_argument_hash
from sentinelllm.approvals.service import ApprovalService
from sentinelllm.contracts.audit import AuditEvent
from sentinelllm.contracts.decision import Decision
from sentinelllm.db.approval_store import PostgresApprovalStore, SqlApprovalStore
from sentinelllm.db.audit_store import SqlAuditStore
from sentinelllm.db.config import DatabaseConfig, get_engine, get_session_factory
from sentinelllm.db.models import (
    ApprovalRequestModel,
    AuditEventModel,
    Base,
    BenchmarkRunModel,
    PolicyVersionModel,
)
from sentinelllm.policy.engine import (
    REASON_DENY_APPROVAL_ACTION_MISMATCH,
    REASON_DENY_APPROVAL_ALREADY_CONSUMED,
    REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH,
    REASON_DENY_APPROVAL_EXPIRED,
    REASON_DENY_APPROVAL_POLICY_MISMATCH,
    REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH,
    REASON_DENY_APPROVAL_TOOL_MISMATCH,
)
from sentinelllm.policy.principal import AuthenticatedPrincipal


@pytest.fixture
def test_db_engine() -> Generator[Engine, None, None]:
    """Create an isolated in-memory SQLite database engine with all tables created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session_factory(test_db_engine: Engine) -> sessionmaker[Session]:
    """Create a sessionmaker bound to the test engine."""
    return sessionmaker(bind=test_db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def sql_approval_store(session_factory: sessionmaker[Session]) -> SqlApprovalStore:
    """Create a SqlApprovalStore bound to test session factory."""
    return SqlApprovalStore(session_factory)


@pytest.fixture
def sql_audit_store(session_factory: sessionmaker[Session]) -> SqlAuditStore:
    """Create a SqlAuditStore bound to test session factory."""
    return SqlAuditStore(session_factory)


@pytest.fixture
def admin_principal() -> AuthenticatedPrincipal:
    """Admin principal with approval management permission."""
    return AuthenticatedPrincipal(
        principal_id="sec_admin_01",
        permissions=frozenset({"approvals:manage"}),
        roles=frozenset({"admin"}),
    )


@pytest.fixture
def user_principal() -> AuthenticatedPrincipal:
    """Standard authenticated principal requesting sensitive action."""
    return AuthenticatedPrincipal(
        principal_id="analyst_user_01",
        permissions=frozenset({"records:export"}),
    )


class TestDatabaseConfig:
    """Verify database configuration, pooling, and credential masking."""

    def test_safe_url_masks_passwords(self) -> None:
        config = DatabaseConfig(
            database_url="postgresql+psycopg://secops:SuperSecretP@ss@db.internal:5432/sentinel_prod"
        )
        safe = config.get_safe_url()
        assert "SuperSecretP@ss" not in safe
        assert "***" in safe
        assert "db.internal:5432/sentinel_prod" in safe

    def test_from_env_defaults_in_development(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = DatabaseConfig.from_env()
            assert config.database_url.startswith("sqlite:///")

    def test_from_env_requires_explicit_url_in_production(self) -> None:
        with (
            patch.dict(os.environ, {"SENTINELLLM_ENV": "production"}, clear=True),
            pytest.raises(ValueError, match=r"Explicit DATABASE_URL.*required in production"),
        ):
            DatabaseConfig.from_env()

    def test_from_env_accepts_custom_database_url(self) -> None:
        custom_url = "postgresql+psycopg://user:pass@localhost:5432/testdb"
        with patch.dict(os.environ, {"SENTINELLLM_DATABASE_URL": custom_url}, clear=True):
            config = DatabaseConfig.from_env()
            assert config.database_url == custom_url

    def test_get_engine_and_session_factory_helpers(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        assert engine is not None
        factory = get_session_factory(engine)
        assert factory is not None
        engine.dispose()

    def test_create_engine_postgres_pooling_parameters(self) -> None:
        config = DatabaseConfig(
            database_url="postgresql+psycopg://user:pass@localhost:5432/test_db",
            pool_size=10,
            max_overflow=20,
        )
        with patch("sentinelllm.db.config.create_engine") as mock_ce:
            config.create_engine()
            mock_ce.assert_called_once()
            _, kwargs = mock_ce.call_args
            assert kwargs["pool_size"] == 10
            assert kwargs["max_overflow"] == 20
            assert kwargs["pool_pre_ping"] is True

    def test_store_invalid_initialization_types(self) -> None:
        with pytest.raises(TypeError, match="Expected Engine or sessionmaker"):
            SqlApprovalStore("invalid_type")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="Expected Engine or sessionmaker"):
            SqlAuditStore("invalid_type")  # type: ignore[arg-type]


class TestOrmDomainConversions:
    """Verify round-trip fidelity between frozen domain objects and ORM entities."""

    def test_approval_request_round_trip(self) -> None:
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=300)
        domain = ApprovalRequest(
            approval_id="app_12345",
            request_id="req_98765",
            principal_id="prin_admin",
            tool_name="database_query",
            action_name="tools:execute:database_query",
            argument_hash="a" * 64,
            policy_version="1.0.0",
            status=ApprovalStatus.APPROVED,
            created_at=now,
            expires_at=expires,
            reviewed_by="supervisor",
            reviewed_at=now,
            consumed_at=None,
        )

        model = ApprovalRequestModel.from_domain(domain)
        restored = model.to_domain()

        assert restored.approval_id == domain.approval_id
        assert restored.request_id == domain.request_id
        assert restored.principal_id == domain.principal_id
        assert restored.status == ApprovalStatus.APPROVED
        assert restored.argument_hash == domain.argument_hash
        assert restored.created_at == domain.created_at

    def test_audit_event_round_trip(self) -> None:
        now = datetime.now(UTC)
        domain = AuditEvent(
            event_id="evt_001",
            request_id="req_001",
            event_type="security.detection",
            timestamp=now,
            component="heuristic_scanner",
            decision=Decision.BLOCK,
            policy_version="2.1.0",
            metadata={"findings_count": 2, "scanner": "canary_leak"},
        )

        model = AuditEventModel.from_domain(domain)
        restored = model.to_domain()

        assert restored.event_id == domain.event_id
        assert restored.request_id == domain.request_id
        assert restored.decision == Decision.BLOCK
        assert restored.metadata == {"findings_count": 2, "scanner": "canary_leak"}

    def test_policy_version_and_benchmark_run_models(
        self, session_factory: sessionmaker[Session]
    ) -> None:
        now = datetime.now(UTC)
        with session_factory() as session, session.begin():
            pol = PolicyVersionModel(
                version_id="pv_01",
                policy_version="v1.0.0",
                content="rules: []",
                created_at=now,
                created_by="admin",
                is_active=True,
            )
            session.add(pol)

            bm = BenchmarkRunModel(
                run_id="bm_01",
                benchmark_name="PromptProbe-v1",
                timestamp=now,
                total_cases=23,
                passed_cases=23,
                failed_cases=0,
                metrics={"accuracy": 1.0},
                environment_info={"os": "darwin"},
            )
            session.add(bm)

        with session_factory() as session:
            fetched_pol = session.get(PolicyVersionModel, "pv_01")
            assert fetched_pol is not None
            assert fetched_pol.policy_version == "v1.0.0"

            fetched_bm = session.get(BenchmarkRunModel, "bm_01")
            assert fetched_bm is not None
            assert fetched_bm.passed_cases == 23


class TestSqlApprovalStore:
    """Verify approval store persistence, approval transitions, and validations."""

    def test_crud_and_listing(self, sql_approval_store: SqlApprovalStore) -> None:
        now = datetime.now(UTC)
        req = ApprovalRequest(
            approval_id="app_test_1",
            request_id="req_test_1",
            principal_id="user_1",
            tool_name="export_tool",
            action_name="tools:execute:export_tool",
            argument_hash="b" * 64,
            policy_version="1.0.0",
            status=ApprovalStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(seconds=60),
        )
        sql_approval_store.save(req)

        fetched = sql_approval_store.get("app_test_1")
        assert fetched is not None
        assert fetched.approval_id == "app_test_1"

        all_reqs = sql_approval_store.list_all()
        assert len(all_reqs) == 1

        sql_approval_store.clear()
        assert len(sql_approval_store.list_all()) == 0

    def test_service_lifecycle_with_sql_store(
        self,
        sql_approval_store: SqlApprovalStore,
        admin_principal: AuthenticatedPrincipal,
        user_principal: AuthenticatedPrincipal,
    ) -> None:
        service = ApprovalService(store=sql_approval_store)
        arg_hash = compute_argument_hash({"account_id": "ACC-9921"})

        # 1. Create approval
        rec, create_audit = service.create_approval(
            request_id="req_lifecycle_1",
            principal_id=user_principal.principal_id,
            tool_name="account_export",
            action_name="tools:execute:account_export",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        assert rec.status == ApprovalStatus.PENDING
        assert create_audit.decision == Decision.REVIEW

        # 2. Cannot consume PENDING
        ok, reason, _ = service.consume(
            approval_id=rec.approval_id,
            principal=user_principal,
            tool_name="account_export",
            action_name="tools:execute:account_export",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        assert not ok
        assert reason == "DENY_APPROVAL_PENDING"

        # 3. Approve
        approved_rec, app_audit = service.approve(rec.approval_id, approver=admin_principal)
        assert approved_rec.status == ApprovalStatus.APPROVED
        assert app_audit.decision == Decision.ALLOW

        # 4. Consume approved
        ok, reason, consumed_audit = service.consume(
            approval_id=rec.approval_id,
            principal=user_principal,
            tool_name="account_export",
            action_name="tools:execute:account_export",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        assert ok
        assert reason == "APPROVAL_CONSUMED"
        assert consumed_audit.decision == Decision.ALLOW

        # 5. Double-spend rejection
        ok, reason, _ = service.consume(
            approval_id=rec.approval_id,
            principal=user_principal,
            tool_name="account_export",
            action_name="tools:execute:account_export",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_ALREADY_CONSUMED

    def test_rejection_lifecycle(
        self,
        sql_approval_store: SqlApprovalStore,
        admin_principal: AuthenticatedPrincipal,
        user_principal: AuthenticatedPrincipal,
    ) -> None:
        service = ApprovalService(store=sql_approval_store)
        arg_hash = "c" * 64

        rec, _ = service.create_approval(
            request_id="req_reject_1",
            principal_id=user_principal.principal_id,
            tool_name="delete_account",
            action_name="tools:execute:delete_account",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )

        service.reject(rec.approval_id, approver=admin_principal, reason="Unauthorized account")

        ok, reason, _ = service.consume(
            approval_id=rec.approval_id,
            principal=user_principal,
            tool_name="delete_account",
            action_name="tools:execute:delete_account",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        assert not ok
        assert reason == "DENY_APPROVAL_REJECTED"

    def test_tampering_and_mismatch_rejections(
        self,
        sql_approval_store: SqlApprovalStore,
        admin_principal: AuthenticatedPrincipal,
        user_principal: AuthenticatedPrincipal,
    ) -> None:
        service = ApprovalService(store=sql_approval_store)
        arg_hash = "d" * 64

        rec, _ = service.create_approval(
            request_id="req_tamper_1",
            principal_id=user_principal.principal_id,
            tool_name="transfer_funds",
            action_name="tools:execute:transfer_funds",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        service.approve(rec.approval_id, approver=admin_principal)

        # Principal mismatch
        other_user = AuthenticatedPrincipal(principal_id="impostor_user")
        ok, reason, _ = service.consume(
            rec.approval_id,
            other_user,
            "transfer_funds",
            "tools:execute:transfer_funds",
            arg_hash,
            "1.0.0",
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH

        # Tool mismatch
        ok, reason, _ = service.consume(
            rec.approval_id,
            user_principal,
            "wrong_tool",
            "tools:execute:transfer_funds",
            arg_hash,
            "1.0.0",
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_TOOL_MISMATCH

        # Action mismatch
        ok, reason, _ = service.consume(
            rec.approval_id,
            user_principal,
            "transfer_funds",
            "tools:execute:wrong_action",
            arg_hash,
            "1.0.0",
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_ACTION_MISMATCH

        # Argument hash mismatch
        ok, reason, _ = service.consume(
            rec.approval_id,
            user_principal,
            "transfer_funds",
            "tools:execute:transfer_funds",
            "e" * 64,
            "1.0.0",
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH

        # Policy version mismatch
        ok, reason, _ = service.consume(
            rec.approval_id,
            user_principal,
            "transfer_funds",
            "tools:execute:transfer_funds",
            arg_hash,
            "2.0.0",
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_POLICY_MISMATCH

    def test_expiry_handling(
        self,
        sql_approval_store: SqlApprovalStore,
        admin_principal: AuthenticatedPrincipal,
        user_principal: AuthenticatedPrincipal,
    ) -> None:
        clock_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        service = ApprovalService(store=sql_approval_store, clock=lambda: clock_time)

        rec, _ = service.create_approval(
            request_id="req_expire_1",
            principal_id=user_principal.principal_id,
            tool_name="backup_system",
            action_name="tools:execute:backup_system",
            argument_hash="a" * 64,
            policy_version="1.0.0",
            ttl_seconds=60,
        )
        service.approve(rec.approval_id, approver=admin_principal)

        # Advance time past expiration
        clock_time = clock_time + timedelta(seconds=61)

        ok, reason, event = service.consume(
            approval_id=rec.approval_id,
            principal=user_principal,
            tool_name="backup_system",
            action_name="tools:execute:backup_system",
            argument_hash="a" * 64,
            policy_version="1.0.0",
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_EXPIRED
        assert event.event_type == "approval.expired"


class TestConcurrencyAndLocking:
    """Stress test multi-worker concurrency and atomic consumption."""

    def test_concurrent_consumption_single_winner(
        self,
        sql_approval_store: SqlApprovalStore,
        admin_principal: AuthenticatedPrincipal,
        user_principal: AuthenticatedPrincipal,
    ) -> None:
        """Simulate multiple concurrent worker threads racing to consume the same approval.

        Verifies that exactly 1 thread succeeds and all others are rejected with
        REASON_DENY_APPROVAL_ALREADY_CONSUMED, guaranteeing single-use semantics.
        """
        service = ApprovalService(store=sql_approval_store)
        arg_hash = "1" * 64

        rec, _ = service.create_approval(
            request_id="req_concurrency_race",
            principal_id=user_principal.principal_id,
            tool_name="sensitive_wire_transfer",
            action_name="tools:execute:sensitive_wire_transfer",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        service.approve(rec.approval_id, approver=admin_principal)

        num_threads = 12
        barrier = threading.Barrier(num_threads)
        results: list[tuple[bool, str]] = []
        lock = threading.Lock()

        def worker() -> None:
            barrier.wait()  # Synchronize thread launch for maximum contention
            ok, reason, _ = service.consume(
                approval_id=rec.approval_id,
                principal=user_principal,
                tool_name="sensitive_wire_transfer",
                action_name="tools:execute:sensitive_wire_transfer",
                argument_hash=arg_hash,
                policy_version="1.0.0",
            )
            with lock:
                results.append((ok, reason))

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r[0] is True]
        failures = [r for r in results if r[0] is False]

        assert len(successes) == 1
        assert successes[0][1] == "APPROVAL_CONSUMED"
        assert len(failures) == num_threads - 1
        for fail in failures:
            assert fail[1] == REASON_DENY_APPROVAL_ALREADY_CONSUMED

        # Verify database record state is consumed
        final_record = sql_approval_store.get(rec.approval_id)
        assert final_record is not None
        assert final_record.status == ApprovalStatus.CONSUMED

    def test_legacy_store_without_atomic_consume_fallback(
        self,
        admin_principal: AuthenticatedPrincipal,
        user_principal: AuthenticatedPrincipal,
    ) -> None:
        """Verify that ApprovalService safely falls back when a store lacks atomic_consume."""

        class LegacyStore:
            def __init__(self) -> None:
                self.records: dict[str, ApprovalRequest] = {}

            def save(self, record: ApprovalRequest) -> None:
                self.records[record.approval_id] = record

            def get(self, approval_id: str) -> ApprovalRequest | None:
                return self.records.get(approval_id)

        legacy = LegacyStore()
        service = ApprovalService(store=legacy)
        arg_hash = "9" * 64

        rec, _ = service.create_approval(
            request_id="req_legacy_1",
            principal_id=user_principal.principal_id,
            tool_name="legacy_action",
            action_name="tools:execute:legacy_action",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        service.approve(rec.approval_id, approver=admin_principal)

        ok, reason, audit = service.consume(
            approval_id=rec.approval_id,
            principal=user_principal,
            tool_name="legacy_action",
            action_name="tools:execute:legacy_action",
            argument_hash=arg_hash,
            policy_version="1.0.0",
        )
        assert ok
        assert reason == "APPROVAL_CONSUMED"
        assert audit.decision == Decision.ALLOW

    def test_postgres_approval_store_alias(self, session_factory: sessionmaker[Session]) -> None:
        """Verify PostgresApprovalStore works as an alias for SqlApprovalStore."""
        store = PostgresApprovalStore(session_factory)
        assert isinstance(store, SqlApprovalStore)


class TestSqlAuditStore:
    """Verify durable audit event persistence and credential exfiltration defenses."""

    def test_save_and_query_events(self, sql_audit_store: SqlAuditStore) -> None:
        now = datetime.now(UTC)
        ev1 = AuditEvent(
            request_id="req_audit_100",
            event_type="policy.decision",
            timestamp=now,
            component="pdp",
            decision=Decision.ALLOW,
            policy_version="1.0.0",
            metadata={"rule_id": "rule_allow_safe_read"},
        )
        ev2 = AuditEvent(
            request_id="req_audit_100",
            event_type="tool.executed",
            timestamp=now + timedelta(milliseconds=10),
            component="pep",
            decision=Decision.ALLOW,
            policy_version="1.0.0",
            metadata={"tool_name": "read_records"},
        )
        ev3 = AuditEvent(
            request_id="req_audit_200",
            event_type="security.blocked",
            timestamp=now + timedelta(milliseconds=20),
            component="pep",
            decision=Decision.BLOCK,
            policy_version="1.0.0",
            metadata={"reason": "policy_denied"},
        )

        sql_audit_store.save_batch([ev1, ev2, ev3])

        # Query all
        all_events = sql_audit_store.query()
        assert len(all_events) == 3

        # Query by request_id
        req100_events = sql_audit_store.query(request_id="req_audit_100")
        assert len(req100_events) == 2

        # Query by event_type
        blocked_events = sql_audit_store.query(event_type="security.blocked")
        assert len(blocked_events) == 1
        assert blocked_events[0].decision == Decision.BLOCK

        # Clear
        sql_audit_store.clear()
        assert len(sql_audit_store.query()) == 0

    def test_metadata_credential_scanning_rejection(self, sql_audit_store: SqlAuditStore) -> None:
        """Verify SqlAuditStore strictly rejects sensitive payload keys."""
        with pytest.raises(ValueError, match="Disallowed audit metadata key"):
            # Construct dictionary that would violate audit scanning
            bad_event = AuditEvent(
                request_id="req_audit_leak",
                event_type="test.leak",
                component="test",
                metadata={"safe_counter": 1},
            )
            # Simulate manual bypass injection into metadata dictionary
            object.__setattr__(bad_event, "metadata", {"api_key": "sk-secret123"})
            sql_audit_store.save(bad_event)
