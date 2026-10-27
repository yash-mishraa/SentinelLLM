"""Database-backed approval store with concurrency and row-level locking support."""

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sentinelllm.approvals.models import ApprovalRequest, ApprovalStatus
from sentinelllm.db.config import DatabaseConfig
from sentinelllm.db.models import ApprovalRequestModel
from sentinelllm.policy.engine import (
    REASON_DENY_APPROVAL_ACTION_MISMATCH,
    REASON_DENY_APPROVAL_ALREADY_CONSUMED,
    REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH,
    REASON_DENY_APPROVAL_EXPIRED,
    REASON_DENY_APPROVAL_POLICY_MISMATCH,
    REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH,
    REASON_DENY_APPROVAL_REJECTED,
    REASON_DENY_APPROVAL_TOOL_MISMATCH,
    REASON_DENY_APPROVAL_UNKNOWN,
)


class SqlApprovalStore:
    """Database-backed approval request repository supporting multi-worker concurrency.

    Concurrency Guarantees:
    - PostgreSQL / standard SQL engines: Applies SELECT ... FOR UPDATE row-level locking
      during state transitions.
    - Defense-in-depth across all dialects (including SQLite): Enforces atomic conditional
      UPDATE statements (`WHERE approval_id = :id AND status = 'APPROVED'`) to guarantee
      single-use test-and-set semantics even under high concurrency.
    """

    def __init__(
        self,
        engine_or_factory: Engine | sessionmaker[Session] | None = None,
    ) -> None:
        if isinstance(engine_or_factory, sessionmaker):
            self.session_factory = engine_or_factory
        elif isinstance(engine_or_factory, Engine):
            self.session_factory = sessionmaker(
                bind=engine_or_factory, autoflush=False, expire_on_commit=False
            )
        elif engine_or_factory is None:
            config = DatabaseConfig.from_env()
            self.session_factory = config.create_session_factory()
        else:
            raise TypeError(
                f"Expected Engine or sessionmaker, got {type(engine_or_factory).__name__}"
            )

    def _supports_for_update(self, session: Session) -> bool:
        """Determine whether the underlying database dialect supports row-level locking."""
        bind = session.get_bind()
        # SQLite does not support FOR UPDATE row locking
        return bind.dialect.name != "sqlite"

    def save(self, record: ApprovalRequest) -> None:
        """Persist or update an approval record."""
        with self.session_factory() as session, session.begin():
            model = ApprovalRequestModel.from_domain(record)
            session.merge(model)

    def get(self, approval_id: str) -> ApprovalRequest | None:
        """Retrieve an approval record by identifier."""
        with self.session_factory() as session:
            model = session.get(ApprovalRequestModel, approval_id)
            return model.to_domain() if model is not None else None

    def list_all(self) -> list[ApprovalRequest]:
        """List all approval requests ordered by creation time."""
        with self.session_factory() as session:
            stmt = select(ApprovalRequestModel).order_by(ApprovalRequestModel.created_at.desc())
            models = session.execute(stmt).scalars().all()
            return [m.to_domain() for m in models]

    def query(
        self,
        status: str | None = None,
        principal_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequest]:
        """Query approval records with optional filtering and bounded pagination."""
        with self.session_factory() as session:
            stmt = select(ApprovalRequestModel)
            if status:
                stmt = stmt.where(ApprovalRequestModel.status == status.upper())
            if principal_id:
                stmt = stmt.where(ApprovalRequestModel.principal_id == principal_id)
            stmt = (
                stmt.order_by(ApprovalRequestModel.created_at.desc())
                .limit(min(max(1, limit), 100))
                .offset(max(0, offset))
            )
            models = session.execute(stmt).scalars().all()
            return [m.to_domain() for m in models]

    def clear(self) -> None:
        """Clear all stored approval records (used for test teardown)."""
        with self.session_factory() as session, session.begin():
            session.execute(delete(ApprovalRequestModel))

    def atomic_consume(
        self,
        approval_id: str,
        principal_id: str,
        tool_name: str,
        action_name: str,
        argument_hash: str,
        policy_version: str,
        now: datetime,
    ) -> tuple[bool, str, ApprovalRequest | None]:
        """Atomically validate and transition an approval record from APPROVED to CONSUMED.

        Uses row-level locking (on supported engines) and conditional test-and-set UPDATEs
        to eliminate TOCTOU race conditions across distributed cluster workers.
        """
        with self.session_factory() as session, session.begin():
            stmt = select(ApprovalRequestModel).where(
                ApprovalRequestModel.approval_id == approval_id
            )
            if self._supports_for_update(session):
                stmt = stmt.with_for_update()

            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                return False, REASON_DENY_APPROVAL_UNKNOWN, None

            domain_rec = row.to_domain()

            # 1. Expiry check
            if now >= domain_rec.expires_at and domain_rec.status in (
                ApprovalStatus.PENDING,
                ApprovalStatus.APPROVED,
            ):
                row.status = ApprovalStatus.EXPIRED.value
                session.flush()
                return False, REASON_DENY_APPROVAL_EXPIRED, domain_rec

            # 2. Status check
            if domain_rec.status == ApprovalStatus.PENDING:
                return False, "DENY_APPROVAL_PENDING", domain_rec
            if domain_rec.status == ApprovalStatus.REJECTED:
                return False, REASON_DENY_APPROVAL_REJECTED, domain_rec
            if domain_rec.status == ApprovalStatus.CONSUMED:
                return False, REASON_DENY_APPROVAL_ALREADY_CONSUMED, domain_rec
            if domain_rec.status == ApprovalStatus.EXPIRED:
                return False, REASON_DENY_APPROVAL_EXPIRED, domain_rec

            # 3. Exact request binding checks
            if domain_rec.principal_id != principal_id:
                return False, REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH, domain_rec
            if domain_rec.tool_name != tool_name:
                return False, REASON_DENY_APPROVAL_TOOL_MISMATCH, domain_rec
            if domain_rec.action_name != action_name:
                return False, REASON_DENY_APPROVAL_ACTION_MISMATCH, domain_rec
            if domain_rec.argument_hash != argument_hash:
                return False, REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH, domain_rec
            if domain_rec.policy_version != policy_version:
                return False, REASON_DENY_APPROVAL_POLICY_MISMATCH, domain_rec

            # 4. Atomic conditional test-and-set
            update_stmt = (
                update(ApprovalRequestModel)
                .where(
                    ApprovalRequestModel.approval_id == approval_id,
                    ApprovalRequestModel.status == ApprovalStatus.APPROVED.value,
                )
                .values(
                    status=ApprovalStatus.CONSUMED.value,
                    consumed_at=now,
                )
            )
            res = session.execute(update_stmt)
            rowcount = getattr(res, "rowcount", -1)
            if rowcount != 1:
                # Double-spend detected concurrently
                return False, REASON_DENY_APPROVAL_ALREADY_CONSUMED, domain_rec

            consumed_domain = domain_rec.model_copy(
                update={"status": ApprovalStatus.CONSUMED, "consumed_at": now}
            )
            return True, "APPROVAL_CONSUMED", consumed_domain


# PostgresApprovalStore alias for PostgreSQL-specific distributed deployments
PostgresApprovalStore = SqlApprovalStore
