"""Multi-worker rate limiting subsystem for SentinelLLM REST Gateway."""

import threading
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from sentinelllm.db.models import RateLimitBucketModel


class BaseRateLimiter(ABC):
    """Abstract interface for request rate limiters."""

    @abstractmethod
    def check_rate_limit(
        self,
        key: str,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> tuple[bool, int, float]:
        """Check whether the request under `key` is permitted.

        Returns:
            Tuple of (is_allowed: bool, remaining_requests: int, reset_after_seconds: float).
        """
        pass


class SqlRateLimiter(BaseRateLimiter):
    """Database-backed rate limiter synchronizing request quotas across distributed workers.

    Architecture:
    Tracks request buckets in the `rate_limit_buckets` table. Each worker transaction
    inspects or creates the bucket row atomically. When window expiration occurs,
    the counter automatically resets to 1.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def check_rate_limit(
        self,
        key: str,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> tuple[bool, int, float]:
        now = datetime.now(UTC)

        for attempt in range(5):
            try:
                with self.session_factory() as session, session.begin():
                    # Query existing bucket
                    stmt = select(RateLimitBucketModel).where(
                        RateLimitBucketModel.bucket_key == key
                    )
                    # Only use for_update on non-sqlite databases
                    bind = session.get_bind()
                    if bind.dialect.name != "sqlite":
                        stmt = stmt.with_for_update()

                    row = session.execute(stmt).scalar_one_or_none()

                    if row is None:
                        # Create initial bucket
                        new_bucket = RateLimitBucketModel(
                            bucket_key=key,
                            window_start=now,
                            request_count=1,
                        )
                        session.add(new_bucket)
                        return True, max(0, max_requests - 1), float(window_seconds)

                    # Ensure UTC timezone awareness on stored window_start
                    w_start = row.window_start
                    if w_start.tzinfo is None:
                        w_start = w_start.replace(tzinfo=UTC)
                    else:
                        w_start = w_start.astimezone(UTC)

                    # Check if current window has expired
                    elapsed = (now - w_start).total_seconds()
                    if elapsed >= window_seconds:
                        # Window expired: reset window
                        row.window_start = now
                        row.request_count = 1
                        return True, max(0, max_requests - 1), float(window_seconds)

                    # Inside window: check count
                    reset_after = max(0.0, window_seconds - elapsed)
                    if row.request_count >= max_requests:
                        # Rate limit exceeded
                        return False, 0, reset_after

                    # Increment count
                    row.request_count += 1
                    remaining = max(0, max_requests - row.request_count)
                    return True, remaining, reset_after
            except (IntegrityError, DBAPIError):
                # Concurrent worker created or modified bucket simultaneously; retry
                if attempt < 4:
                    time.sleep(0.02 * (attempt + 1))
                    continue
                raise

        return False, 0, float(window_seconds)

    def clear(self) -> None:
        """Clear all rate limit records (for testing)."""
        with self.session_factory() as session, session.begin():
            session.execute(delete(RateLimitBucketModel))


class InMemoryRateLimiter(BaseRateLimiter):
    """Process-local thread-safe rate limiter for fast unit testing and standalone mode."""

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[datetime, int]] = {}
        self._lock = threading.Lock()

    def check_rate_limit(
        self,
        key: str,
        max_requests: int = 60,
        window_seconds: int = 60,
    ) -> tuple[bool, int, float]:
        now = datetime.now(UTC)
        with self._lock:
            record = self._buckets.get(key)
            if record is None:
                self._buckets[key] = (now, 1)
                return True, max(0, max_requests - 1), float(window_seconds)

            w_start, count = record
            elapsed = (now - w_start).total_seconds()

            if elapsed >= window_seconds:
                self._buckets[key] = (now, 1)
                return True, max(0, max_requests - 1), float(window_seconds)

            reset_after = max(0.0, window_seconds - elapsed)
            if count >= max_requests:
                return False, 0, reset_after

            self._buckets[key] = (w_start, count + 1)
            return True, max(0, max_requests - (count + 1)), reset_after

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()
