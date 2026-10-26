"""Typed contracts and models for the human approval workflow."""

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApprovalStatus(StrEnum):
    """Lifecycle states for human approval requests."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


def compute_argument_hash(arguments: BaseModel | dict[str, Any]) -> str:
    """Compute a deterministic, canonical SHA-256 digest of tool arguments.

    Prevents argument tampering between authorization review and execution.
    """
    if isinstance(arguments, BaseModel):
        data = arguments.model_dump(mode="json")
    elif isinstance(arguments, dict):
        data = arguments
    else:
        raise TypeError(f"Expected BaseModel or dict, got {type(arguments).__name__}")

    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ApprovalRequest(BaseModel):
    """Immutable record representing a human authorization approval request.

    Security Invariant:
    Approvals are bound to the exact requesting principal, tool, action,
    canonical argument digest, and policy version. Approvals expire, are
    single-use, and never store raw sensitive arguments or customer payloads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    approval_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    principal_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    action_name: str = Field(min_length=1)
    argument_hash: str = Field(min_length=64, max_length=64)
    policy_version: str = Field(min_length=1)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime
    expires_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    consumed_at: datetime | None = None

    @field_validator("created_at", "expires_at", "reviewed_at", "consumed_at")
    @classmethod
    def _assert_utc_timestamp(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)
