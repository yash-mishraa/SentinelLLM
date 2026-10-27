"""Cryptographic authentication and authorization for the SentinelLLM REST Gateway."""

import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, status
from fastapi.security import APIKeyHeader

from sentinelllm.policy.principal import AuthenticatedPrincipal

logger = logging.getLogger("sentinelllm.api.auth")

# Header-based API key extractor
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# Insecure development keys that must never be permitted in production
INSECURE_DEV_KEYS: frozenset[str] = frozenset(
    {
        "sentinel-admin-key-secret",
        "sentinel-analyst-key-secret",
        "sentinel-supervisor-key-secret",
        "sentinel-guest-key-secret",
        "dev-analyst-key-12345",
        "dev-supervisor-key-67890",
        "dev-admin-key-99999",
    }
)


@dataclass(frozen=True)
class ApiKeyRecord:
    """Immutable metadata record corresponding to a hashed API key."""

    key_hash: str
    principal_id: str
    roles: frozenset[str]
    permissions: frozenset[str]


def hash_api_key(raw_key: str) -> str:
    """Compute deterministic SHA-256 digest of an API key.

    Security Invariant:
    Raw API keys must never be stored in memory registries, database records,
    or written to log telemetry. Only the SHA-256 verifier hash is preserved.
    """
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


class ApiKeyRegistry:
    """Thread-safe in-memory cache of hashed API keys and associated principals."""

    def __init__(self) -> None:
        self._records: dict[str, ApiKeyRecord] = {}

    def register_key(
        self,
        raw_key: str,
        principal_id: str,
        roles: set[str] | frozenset[str] | list[str] | None = None,
        permissions: set[str] | frozenset[str] | list[str] | None = None,
    ) -> str:
        """Register an API key by computing and storing its hash.

        Returns:
            The SHA-256 digest of the registered key.
        """
        digest = hash_api_key(raw_key)
        self._records[digest] = ApiKeyRecord(
            key_hash=digest,
            principal_id=principal_id,
            roles=frozenset(roles or []),
            permissions=frozenset(permissions or []),
        )
        return digest

    def register_hash(
        self,
        key_hash: str,
        principal_id: str,
        roles: set[str] | frozenset[str] | list[str] | None = None,
        permissions: set[str] | frozenset[str] | list[str] | None = None,
    ) -> None:
        """Directly register a precomputed SHA-256 API key hash."""
        self._records[key_hash] = ApiKeyRecord(
            key_hash=key_hash,
            principal_id=principal_id,
            roles=frozenset(roles or []),
            permissions=frozenset(permissions or []),
        )

    def lookup(self, raw_key: str) -> AuthenticatedPrincipal | None:
        """Verify an incoming API key using constant-time comparison against registered hashes."""
        if not raw_key or len(raw_key.strip()) < 8:
            return None

        incoming_hash = hash_api_key(raw_key)
        matched_record: ApiKeyRecord | None = None
        for stored_hash, record in self._records.items():
            if secrets.compare_digest(incoming_hash, stored_hash):
                matched_record = record

        if matched_record is not None:
            return AuthenticatedPrincipal(
                principal_id=matched_record.principal_id,
                roles=matched_record.roles,
                permissions=matched_record.permissions,
            )
        return None

    def clear(self) -> None:
        """Clear all registered API key records (for testing)."""
        self._records.clear()

    @classmethod
    def create_default(
        cls, api_keys_json: str | None = None, is_production: bool = False
    ) -> "ApiKeyRegistry":
        """Factory creating registry populated from environment JSON or dev defaults."""
        registry = cls()
        if api_keys_json:
            try:
                data = json.loads(api_keys_json)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            raw = item.get("raw_key")
                            khash = item.get("key_hash")
                            pid = item.get("principal_id", "service_user")
                            roles = item.get("roles", [])
                            perms = item.get("permissions", [])
                            if raw:
                                if is_production and raw in INSECURE_DEV_KEYS:
                                    raise ValueError(
                                        f"Insecure development default key '{raw}' "
                                        "cannot be used in production."
                                    )
                                registry.register_key(raw, pid, roles, perms)
                            elif khash:
                                registry.register_hash(khash, pid, roles, perms)
            except Exception as e:
                logger.error(
                    "Failed to parse SENTINELLLM_API_KEYS environment configuration: %s", e
                )
                if is_production:
                    raise ValueError(
                        f"Invalid SENTINELLLM_API_KEYS configuration in production: {e}"
                    ) from e

        if not registry._records:
            # Check individual role keys from environment variables
            admin_key = (
                os.getenv("SENTINELLLM_ADMIN_KEY")
                or os.getenv("SENTINELLLM_ROLE_ADMIN_KEY")
                or os.getenv("SENTINEL_ADMIN_KEY")
            )
            supervisor_key = (
                os.getenv("SENTINELLLM_SUPERVISOR_KEY")
                or os.getenv("SENTINELLLM_ROLE_SUPERVISOR_KEY")
                or os.getenv("SENTINEL_SUPERVISOR_KEY")
            )
            analyst_key = (
                os.getenv("SENTINELLLM_ANALYST_KEY")
                or os.getenv("SENTINELLLM_ROLE_ANALYST_KEY")
                or os.getenv("SENTINEL_ANALYST_KEY")
            )
            guest_key = (
                os.getenv("SENTINELLLM_GUEST_KEY")
                or os.getenv("SENTINELLLM_ROLE_GUEST_KEY")
                or os.getenv("SENTINEL_GUEST_KEY")
            )

            if admin_key:
                if is_production and admin_key in INSECURE_DEV_KEYS:
                    raise ValueError(
                        "Insecure development default admin key cannot be used in production."
                    )
                registry.register_key(admin_key, "sec_admin", ["admin"], ["*"])

            if supervisor_key:
                if is_production and supervisor_key in INSECURE_DEV_KEYS:
                    raise ValueError(
                        "Insecure development default supervisor key cannot be used in production."
                    )
                registry.register_key(
                    supervisor_key,
                    "supervisor_dan",
                    ["supervisor"],
                    ["approvals:manage", "audit:read"],
                )

            if analyst_key:
                if is_production and analyst_key in INSECURE_DEV_KEYS:
                    raise ValueError(
                        "Insecure development default analyst key cannot be used in production."
                    )
                registry.register_key(
                    analyst_key,
                    "analyst_bob",
                    ["analyst"],
                    ["inspect:run", "authorize:run", "records:read", "records:export"],
                )

            if guest_key:
                if is_production and guest_key in INSECURE_DEV_KEYS:
                    raise ValueError(
                        "Insecure development default guest key cannot be used in production."
                    )
                registry.register_key(guest_key, "guest_visitor", ["guest"], ["inspect:run"])

        if not registry._records:
            if is_production:
                raise ValueError(
                    "No API keys configured. In production, SENTINELLLM_API_KEYS or individual "
                    "SENTINELLLM_*_KEY environment variables must be configured."
                )
            # Seed standard development keys for local testing
            registry.register_key(
                raw_key="sentinel-admin-key-secret",
                principal_id="sec_admin",
                roles=["admin"],
                permissions=["*"],
            )
            registry.register_key(
                raw_key="sentinel-analyst-key-secret",
                principal_id="analyst_bob",
                roles=["analyst"],
                permissions=["inspect:run", "authorize:run", "records:read", "records:export"],
            )
            registry.register_key(
                raw_key="sentinel-supervisor-key-secret",
                principal_id="supervisor_dan",
                roles=["supervisor"],
                permissions=["approvals:manage", "audit:read"],
            )
            registry.register_key(
                raw_key="sentinel-guest-key-secret",
                principal_id="guest_visitor",
                roles=["guest"],
                permissions=["inspect:run"],
            )

        return registry


def verify_self_approval(requester_id: str, approver_id: str) -> None:
    """Enforce strict separation of duties: users can never approve their own actions.

    Security Invariant:
    Case folding and whitespace normalization are strictly applied to prevent
    identity spoofing bypasses across casing variations (e.g. 'alice ' vs 'Alice').

    Raises:
        HTTPException: 403 Forbidden if requester matches approver.
    """
    clean_requester = requester_id.strip().casefold()
    clean_approver = approver_id.strip().casefold()
    if not clean_requester or not clean_approver or clean_requester == clean_approver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-approval of sensitive actions is strictly prohibited by security policy.",
        )
