"""Request context contract maintaining ordered context items and execution metadata."""

import re
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinelllm.contracts.messages import SecurityContent

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|password|secret|token|auth(orization)?|private[_-]?key)"
)


class RequestContext(BaseModel):
    """Immutable context container for an inbound request through the security lifecycle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    correlation_id: str | None = None
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
