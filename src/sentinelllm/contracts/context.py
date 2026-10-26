"""Request context contract maintaining ordered context items and execution metadata."""

import re
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinelllm.contracts.messages import SecurityContent
from sentinelllm.policy.principal import AuthenticatedPrincipal

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|password|secret|token|auth(orization)?|private[_-]?key)"
)


class RequestContext(BaseModel):
    """Immutable context container for an inbound request through the security lifecycle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    correlation_id: str | None = None
    principal: AuthenticatedPrincipal | None = None
    items: tuple[SecurityContent, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _reject_sensitive_metadata_keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Assert that no credentials or sensitive tokens are stored in request metadata."""
        for key in v:
            if _SENSITIVE_KEY_PATTERN.search(key):
                raise ValueError(
                    f"Sensitive key pattern detected in metadata: '{key}'. "
                    "Credentials and secrets must never be placed in RequestContext metadata."
                )
        return v


def parse_untrusted_context(payload: dict[str, Any] | str) -> RequestContext:
    """Safely parse untrusted serialized context, preventing identity and instruction escalation.

    Security Invariants:
    1. Caller-supplied payloads can NEVER assert an authenticated principal (is_authenticated=True
       or custom roles/permissions). Any attempt raises ValueError.
    2. All items within the context are strictly parsed through parse_untrusted_content,
       preventing injection of ApplicationInstruction or TRUSTED_INSTRUCTIONS authority.
    3. Metadata is scanned for sensitive key patterns.

    Raises:
        ValueError: If payload attempts identity spoofing or instruction escalation.
        TypeError: If payload is not a dict or string.
    """
    from sentinelllm.contracts.messages import UserMessage, parse_untrusted_content

    if isinstance(payload, str):
        return RequestContext(items=(UserMessage(content=payload),))

    if not isinstance(payload, dict):
        raise TypeError(f"Expected dict or str for untrusted context, got {type(payload).__name__}")

    # Enforce identity boundary: callers cannot assert authenticated identity via untrusted payload
    principal_data = payload.get("principal")
    if principal_data is not None:
        if isinstance(principal_data, dict):
            if principal_data.get("is_authenticated", False):
                raise ValueError(
                    "Security violation: Untrusted serialized context cannot supply "
                    "an authenticated principal."
                )
            if principal_data.get("roles") or principal_data.get("permissions"):
                raise ValueError(
                    "Security violation: Untrusted serialized context cannot "
                    "claim roles or permissions."
                )
        else:
            raise ValueError(
                "Security violation: Untrusted principal specification must be a "
                "dictionary or omitted."
            )

    # Enforce content provenance: all items must parse via parse_untrusted_content
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list | tuple):
        raise TypeError(f"Expected list or tuple for context items, got {type(raw_items).__name__}")

    parsed_items = [parse_untrusted_content(item) for item in raw_items]

    return RequestContext(
        request_id=payload.get("request_id") or uuid4().hex,
        correlation_id=payload.get("correlation_id"),
        principal=None,  # Principal can only be bound out-of-band by verified host session
        items=tuple(parsed_items),
        metadata=payload.get("metadata", {}),
    )
