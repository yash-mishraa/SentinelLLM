"""Automated tests for Alembic schema migrations."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


@pytest.fixture
def temp_alembic_db(tmp_path: Path) -> tuple[str, Path]:
    """Provide a temporary SQLite database path for migration testing."""
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file}"
    return db_url, db_file


def test_alembic_upgrade_and_downgrade(temp_alembic_db: tuple[str, Path]) -> None:
    """Verify that Alembic migrations apply and roll back cleanly."""
    db_url, _ = temp_alembic_db
    project_root = Path(__file__).resolve().parent.parent.parent
    alembic_ini_path = project_root / "alembic.ini"

    assert alembic_ini_path.exists(), f"Missing alembic.ini at {alembic_ini_path}"

    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Check all expected tables exist
    assert "approval_requests" in tables
    assert "audit_events" in tables
    assert "policy_versions" in tables
    assert "benchmark_runs" in tables
    assert "rate_limit_buckets" in tables
    assert "alembic_version" in tables

    # Check approval_requests columns and indexes
    approval_cols = {col["name"] for col in inspector.get_columns("approval_requests")}
    assert "approval_id" in approval_cols
    assert "argument_hash" in approval_cols
    assert "status" in approval_cols
    assert "consumed_at" in approval_cols

    # Check audit_events columns
    audit_cols = {col["name"] for col in inspector.get_columns("audit_events")}
    assert "event_id" in audit_cols
    assert "event_type" in audit_cols
    assert "metadata" in audit_cols

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    inspector_after = inspect(engine)
    tables_after = inspector_after.get_table_names()
    assert "approval_requests" not in tables_after
    assert "audit_events" not in tables_after
    assert "policy_versions" not in tables_after
    assert "benchmark_runs" not in tables_after
    assert "rate_limit_buckets" not in tables_after

    engine.dispose()
