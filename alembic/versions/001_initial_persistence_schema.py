"""Initial database schema for approvals, audit events, policies, and benchmarks.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-26 22:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. approval_requests table
    op.create_table(
        "approval_requests",
        sa.Column("approval_id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("action_name", sa.String(length=256), nullable=False),
        sa.Column("argument_hash", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("approval_id"),
    )
    op.create_index(
        "ix_approval_requests_request_id", "approval_requests", ["request_id"], unique=False
    )
    op.create_index(
        "ix_approval_requests_principal_id", "approval_requests", ["principal_id"], unique=False
    )
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"], unique=False)
    op.create_index(
        "ix_approval_requests_expires_at", "approval_requests", ["expires_at"], unique=False
    )

    # 2. audit_events table
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("component", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("policy_version", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"], unique=False)
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"], unique=False)

    # 3. policy_versions table
    op.create_table(
        "policy_versions",
        sa.Column("version_id", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_policy_versions_policy_version", "policy_versions", ["policy_version"], unique=True
    )

    # 4. benchmark_runs table
    op.create_table(
        "benchmark_runs",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("benchmark_name", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("passed_cases", sa.Integer(), nullable=False),
        sa.Column("failed_cases", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("environment_info", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_benchmark_runs_benchmark_name", "benchmark_runs", ["benchmark_name"], unique=False
    )
    op.create_index("ix_benchmark_runs_timestamp", "benchmark_runs", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_benchmark_runs_timestamp", table_name="benchmark_runs")
    op.drop_index("ix_benchmark_runs_benchmark_name", table_name="benchmark_runs")
    op.drop_table("benchmark_runs")

    op.drop_index("ix_policy_versions_policy_version", table_name="policy_versions")
    op.drop_table("policy_versions")

    op.drop_index("ix_audit_events_timestamp", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_approval_requests_expires_at", table_name="approval_requests")
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_principal_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_request_id", table_name="approval_requests")
    op.drop_table("approval_requests")
