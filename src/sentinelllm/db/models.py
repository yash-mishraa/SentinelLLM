"""Declarative ORM models for SentinelLLM database persistence."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

from sentinelllm.approvals.models import ApprovalRequest, ApprovalStatus
from sentinelllm.contracts.audit import AuditEvent
from sentinelllm.contracts.decision import Decision


class Base(DeclarativeBase):
    """Base declarative class for SentinelLLM schema."""

    pass


class ApprovalRequestModel(Base):
    """Database entity persisting human approval requests across cluster nodes."""

    __tablename__ = "approval_requests"

    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    principal_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    action_name: Mapped[str] = mapped_column(String(256), nullable=False)
    argument_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @classmethod
    def from_domain(cls, domain: ApprovalRequest) -> "ApprovalRequestModel":
        """Convert a frozen domain ApprovalRequest into an ORM model."""
        return cls(
            approval_id=domain.approval_id,
            request_id=domain.request_id,
            principal_id=domain.principal_id,
            tool_name=domain.tool_name,
            action_name=domain.action_name,
            argument_hash=domain.argument_hash,
            policy_version=domain.policy_version,
            status=domain.status.value,
            created_at=domain.created_at,
            expires_at=domain.expires_at,
            reviewed_by=domain.reviewed_by,
            reviewed_at=domain.reviewed_at,
            rejection_reason=domain.rejection_reason,
            consumed_at=domain.consumed_at,
        )

    def to_domain(self) -> ApprovalRequest:
        """Convert an ORM model to a typed domain ApprovalRequest."""

        def _ensure_utc(dt: datetime | None) -> datetime | None:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)

        return ApprovalRequest(
            approval_id=self.approval_id,
            request_id=self.request_id,
            principal_id=self.principal_id,
            tool_name=self.tool_name,
            action_name=self.action_name,
            argument_hash=self.argument_hash,
            policy_version=self.policy_version,
            status=ApprovalStatus(self.status),
            created_at=_ensure_utc(self.created_at),  # type: ignore[arg-type]
            expires_at=_ensure_utc(self.expires_at),  # type: ignore[arg-type]
            reviewed_by=self.reviewed_by,
            reviewed_at=_ensure_utc(self.reviewed_at),
            rejection_reason=self.rejection_reason,
            consumed_at=_ensure_utc(self.consumed_at),
        )


class AuditEventModel(Base):
    """Database entity persisting structured security audit records."""

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)

    @classmethod
    def from_domain(cls, domain: AuditEvent) -> "AuditEventModel":
        """Convert a frozen domain AuditEvent into an ORM model."""
        return cls(
            event_id=domain.event_id,
            request_id=domain.request_id,
            event_type=domain.event_type,
            timestamp=domain.timestamp,
            component=domain.component,
            decision=domain.decision.value if domain.decision is not None else None,
            policy_version=domain.policy_version,
            metadata_json=domain.metadata,
        )

    def to_domain(self) -> AuditEvent:
        """Convert an ORM model to a typed domain AuditEvent."""
        ts = self.timestamp
        ts = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)

        decision_enum = Decision(self.decision) if self.decision else None

        return AuditEvent(
            event_id=self.event_id,
            request_id=self.request_id,
            event_type=self.event_type,
            timestamp=ts,
            component=self.component,
            decision=decision_enum,
            policy_version=self.policy_version,
            metadata=self.metadata_json,
        )


class PolicyVersionModel(Base):
    """Database entity persisting versioned security policies."""

    __tablename__ = "policy_versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BenchmarkRunModel(Base):
    """Database entity persisting PromptProbe benchmark execution records."""

    __tablename__ = "benchmark_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    environment_info: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class RateLimitBucketModel(Base):
    """Database entity persisting distributed rate limiting counters across API workers."""

    __tablename__ = "rate_limit_buckets"

    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
