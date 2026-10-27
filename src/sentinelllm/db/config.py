"""Database configuration and session management for SentinelLLM."""

import os
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class DatabaseConfig:
    """Manages database connection parameters, engine pooling, and session factories.

    Security Invariant:
    Database connection URLs containing credentials must never be leaked into logs
    or unauthenticated audit messages. Password masking is enforced by default.
    """

    def __init__(
        self,
        database_url: str = "sqlite:///:memory:",
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: float = 30.0,
    ) -> None:
        self.database_url = database_url
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Instantiate configuration from environment variables.

        Rules:
        1. Checks SENTINELLLM_DATABASE_URL or DATABASE_URL.
        2. In production (SENTINELLLM_ENV='production'), raises an error if an explicit
           database URL is not provided.
        3. In development or test environments, falls back to a local SQLite database
           or in-memory database if USE_SQLITE is specified.
        """
        env_name = os.getenv("SENTINELLLM_ENV", "development").lower()
        db_url = os.getenv("SENTINELLLM_DATABASE_URL") or os.getenv("DATABASE_URL")

        if not db_url:
            if env_name == "production":
                raise ValueError(
                    "Explicit DATABASE_URL or SENTINELLLM_DATABASE_URL is required in production."
                )
            # Default zero-config fallback for dev/test
            db_url = "sqlite:///sentinelllm_dev.db"

        echo = os.getenv("SENTINELLLM_DB_ECHO", "false").lower() in ("true", "1", "yes")
        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://") :]
        return cls(database_url=db_url, echo=echo)

    def get_safe_url(self) -> str:
        """Return the database URL with masked credentials suitable for logging."""
        try:
            return make_url(self.database_url).render_as_string(hide_password=True)
        except Exception:
            parsed = urlparse(self.database_url)
            if parsed.password:
                netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
                return parsed._replace(netloc=netloc).geturl()
            return self.database_url

    def create_engine(self, **engine_kwargs: Any) -> Engine:
        """Create a SQLAlchemy Engine with connection parameters tuned for dialect."""
        url = self.database_url
        kwargs: dict[str, Any] = {"echo": self.echo, **engine_kwargs}

        if url.startswith("sqlite"):
            # SQLite connection tuning
            kwargs.setdefault("connect_args", {"check_same_thread": False})
            if url == "sqlite://" or url == "sqlite:///:memory:":
                # In-memory shared pool for testing
                kwargs.setdefault("poolclass", StaticPool)
        else:
            # PostgreSQL or standard client-server pooling
            kwargs.setdefault("pool_size", self.pool_size)
            kwargs.setdefault("max_overflow", self.max_overflow)
            kwargs.setdefault("pool_timeout", self.pool_timeout)
            kwargs.setdefault("pool_pre_ping", True)

        return create_engine(url, **kwargs)

    def create_session_factory(self, engine: Engine | None = None) -> sessionmaker[Session]:
        """Create a thread-safe sessionmaker bound to an engine."""
        eng = engine or self.create_engine()
        return sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)


def get_engine(database_url: str | None = None) -> Engine:
    """Convenience helper to obtain an Engine from URL or environment."""
    if database_url:
        return DatabaseConfig(database_url=database_url).create_engine()
    return DatabaseConfig.from_env().create_engine()


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Convenience helper to obtain a sessionmaker factory."""
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
