"""Database-backed audit store for tamper-evident security telemetry."""

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sentinelllm.contracts.audit import AuditEvent, _scan_keys_recursively
from sentinelllm.db.config import DatabaseConfig
from sentinelllm.db.models import AuditEventModel


class SqlAuditStore:
    """Database-backed repository for security audit events.

    Security Invariants:
    1. Every audit event metadata payload is validated via _scan_keys_recursively to guarantee
       that raw prompts, documents, credentials, and API tokens are never written to disk.
    2. Audit events are stored in their own transactions to prevent operational rollbacks
       from deleting security telemetry.
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

    def save(self, event: AuditEvent) -> None:
        """Persist a single audit event, verifying zero credential leakage."""
        _scan_keys_recursively(event.metadata)
        with self.session_factory() as session, session.begin():
            model = AuditEventModel.from_domain(event)
            session.merge(model)

    def save_batch(self, events: Sequence[AuditEvent]) -> None:
        """Persist multiple audit events in a single transaction."""
        for event in events:
            _scan_keys_recursively(event.metadata)

        with self.session_factory() as session, session.begin():
            for event in events:
                model = AuditEventModel.from_domain(event)
                session.merge(model)

    def query(
        self,
        request_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Query audit records with filtering and pagination."""
        with self.session_factory() as session:
            stmt = select(AuditEventModel)
            if request_id:
                stmt = stmt.where(AuditEventModel.request_id == request_id)
            if event_type:
                stmt = stmt.where(AuditEventModel.event_type == event_type)

            stmt = stmt.order_by(AuditEventModel.timestamp.asc()).limit(limit).offset(offset)
            rows = session.execute(stmt).scalars().all()
            return [row.to_domain() for row in rows]

    def clear(self) -> None:
        """Clear all audit records (for test isolation)."""
        with self.session_factory() as session, session.begin():
            session.execute(delete(AuditEventModel))
