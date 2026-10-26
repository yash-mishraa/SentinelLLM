"""Authorization request model evaluated by the Policy Decision Point (PDP)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sentinelllm.contracts.decision import SecurityFinding
from sentinelllm.contracts.provenance import TrustClassification
from sentinelllm.policy.principal import AuthenticatedPrincipal


class AuthorizationRequest(BaseModel):
    """Normalized authorization query submitted to the Policy Decision Point."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    principal: AuthenticatedPrincipal | None = None
    action: str = Field(min_length=1)
    resource: str = Field(min_length=1)
    context_trust: TrustClassification = TrustClassification.UNTRUSTED_CONTEXT
    findings: tuple[SecurityFinding, ...] = Field(default_factory=tuple)
    policy_version: str = "1.0.0"
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
