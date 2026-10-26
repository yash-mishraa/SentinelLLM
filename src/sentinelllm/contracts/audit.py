"""Structured audit event contract for security telemetry and audit trails."""

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinelllm.contracts.decision import Decision

_DISALLOWED_AUDIT_KEYS = re.compile(
    r"(?i)(raw_?prompt|prompt_text|document_content|tool_args|raw_content|"
    r"password|secret|api[_-]?key|token|auth(orization)?|private[_-]?key|credential)"
)


def _scan_keys_recursively(data: Any) -> None:
    """Recursively traverse metadata data structures to reject sensitive or credential keys."""
    if isinstance(data, dict):
        for key, val in data.items():
            if _DISALLOWED_AUDIT_KEYS.search(str(key)):
                raise ValueError(
                    f"Disallowed audit metadata key '{key}'. Raw content, prompts, and "
                    "credentials must never be stored in AuditEvent metadata."
                )
            _scan_keys_recursively(val)
    elif isinstance(data, list | tuple | set | frozenset):
        for item in data:
            _scan_keys_recursively(item)


class AuditEvent(BaseModel):
    """Structured audit record emitted at key lifecycle and policy checkpoints.

    Security Invariant:
    Audit events record structural metadata, counts, and security outcomes.
    Raw user prompts, retrieved documents, and tool arguments are strictly excluded
    to prevent sensitive data exfiltration through log channels.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    request_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    component: str = Field(min_length=1)
    decision: Decision | None = None
    policy_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _assert_utc_timestamp(cls, v: datetime) -> datetime:
        """Ensure timestamps are explicitly timezone-aware in UTC."""
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)

    @field_validator("metadata")
    @classmethod
    def _reject_raw_content_in_audit_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Prevent leakage of raw payloads or secrets into audit metadata."""
        _scan_keys_recursively(v)
        return v
