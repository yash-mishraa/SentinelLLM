#!/usr/bin/env python3
"""Standalone Alembic migration runner for SentinelLLM deployment workflows.

Security Invariants:
1. Migrations must execute as an explicit standalone pre-deployment release task,
   never automatically across multi-worker application instances.
2. Production requires explicit DATABASE_URL. Missing credentials fail closed immediately.
3. Database credentials must never be echoed to stdout/stderr.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from alembic import command

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("sentinelllm.migrate")


def get_sanitized_url(raw_url: str) -> str:
    """Mask password credentials in database URL for safe logging."""
    try:
        return make_url(raw_url).render_as_string(hide_password=True)
    except Exception:
        return "database_url_masked"


def resolve_database_url() -> str:
    """Retrieve and normalize database URL from environment."""
    env_name = os.getenv("SENTINELLLM_ENV", "development").lower()
    raw_url = os.getenv("SENTINELLLM_DATABASE_URL") or os.getenv("DATABASE_URL")

    if not raw_url:
        if env_name == "production":
            logger.error("FATAL: DATABASE_URL must be set in production environment.")
            sys.exit(1)
        raw_url = "sqlite:///sentinelllm_dev.db"
        logger.warning("No DATABASE_URL configured. Falling back to local SQLite: %s", raw_url)

    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://") :]

    return raw_url


def run_migrations(action: str = "upgrade", revision: str = "head") -> None:
    """Execute Alembic migration against configured database."""
    db_url = resolve_database_url()
    safe_url = get_sanitized_url(db_url)

    project_root = Path(__file__).resolve().parent.parent
    alembic_ini_path = project_root / "alembic.ini"

    if not alembic_ini_path.exists():
        logger.error("FATAL: Missing alembic.ini at %s", alembic_ini_path)
        sys.exit(1)

    logger.info("Executing database migration '%s %s' against %s", action, revision, safe_url)

    # Pre-flight connectivity check
    try:
        from sqlalchemy import text

        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as conn_err:
        logger.error("Database pre-flight connection failed: %s", conn_err)
        sys.exit(1)

    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    try:
        if action == "upgrade":
            command.upgrade(alembic_cfg, revision)
            logger.info("Database migration upgrade to '%s' completed successfully.", revision)
        elif action == "downgrade":
            command.downgrade(alembic_cfg, revision)
            logger.info("Database migration downgrade to '%s' completed successfully.", revision)
        elif action == "current":
            command.current(alembic_cfg)
        elif action == "heads":
            command.heads(alembic_cfg)
        else:
            logger.error("Unsupported migration action: %s", action)
            sys.exit(1)
    except Exception as exc:
        logger.error("Migration execution failed: %s", exc, exc_info=True)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="SentinelLLM Database Migration Runner")
    parser.add_argument(
        "action",
        nargs="?",
        default="upgrade",
        choices=["upgrade", "downgrade", "current", "heads"],
        help="Migration action to perform (default: upgrade)",
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="head",
        help="Target revision identifier (e.g. 'head', '-1', 'base', default: head)",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Explicit revision identifier overriding target",
    )
    args = parser.parse_args()

    rev = args.revision or args.target
    run_migrations(action=args.action, revision=rev)


if __name__ == "__main__":
    main()
