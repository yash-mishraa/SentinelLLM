"""Security decision and finding contracts.

Defines the output structure for analytical detectors (findings) and
the separate, deterministic policy decisions (enforcement).
"""

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class Decision(StrEnum):
    """Enforcement decision rendered by the policy engine."""

    ALLOW = "allow"
    BLOCK = "block"
    REDACT = "redact"
    REVIEW = "review"


class Severity(StrEnum):
    """Normalized risk severity for analytical detector findings."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityFinding(BaseModel):
    """A distinct analytical observation emitted by a security detector.

    Security Invariant:
    A detector finding is purely analytical telemetry. A finding must never
    independently grant permissions or execute actions; all enforcement authority
    resides solely in the Policy Decision Point (PDP).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Annotated[str, Field(min_length=1)]
    severity: Severity
    source: Annotated[str, Field(min_length=1)]
    explanation: Annotated[str, Field(min_length=1)]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityDecision(BaseModel):
    """The authoritative enforcement outcome rendered for a request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: Decision
    findings: tuple[SecurityFinding, ...] = Field(default_factory=tuple)
    reason: str = ""
    policy_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
