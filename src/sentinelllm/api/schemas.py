"""Pydantic request and response schemas for the SentinelLLM REST Gateway."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health status response."""

    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    version: str = "1.0.0rc1"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReadyResponse(BaseModel):
    """Readiness probe response checking backing services."""

    model_config = ConfigDict(extra="forbid")

    status: str
    database_connected: bool
    policy_engine_ready: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SecurityFindingSchema(BaseModel):
    """Normalized security finding emitted by scanner."""

    model_config = ConfigDict(extra="forbid")

    source: str
    category: str
    severity: str
    explanation: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolSpecResponse(BaseModel):
    """Tool specification metadata for action-level discovery."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    description: str
    action_identifier: str
    resource_classification: str
    is_sensitive: bool
    requires_approval: bool
    argument_schema: dict[str, Any] = Field(default_factory=dict)


class InspectRequest(BaseModel):
    """Inbound content payload for security scanning."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=100_000)
    source_type: str = Field(default="USER_MESSAGE", max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InspectResponse(BaseModel):
    """Security inspection outcome."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    decision: str
    is_safe: bool
    blocked: bool
    findings_count: int
    findings: list[SecurityFindingSchema]


class AuthorizeRequest(BaseModel):
    """Proposed tool action for policy evaluation."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=128)
    action_name: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict)
    policy_version: str | None = Field(default=None, max_length=64)
    declared_principal_id: str | None = Field(default=None, max_length=128)


class AuthorizeResponse(BaseModel):
    """Policy authorization decision."""

    model_config = ConfigDict(extra="forbid")

    decision: str
    reason_code: str
    policy_version: str
    requires_approval: bool
    principal_id: str


class ExecuteRequest(BaseModel):
    """Tool execution request proxied through the PEP."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=128)
    action_name: str = Field(min_length=1, max_length=256)
    arguments: dict[str, Any] = Field(default_factory=dict)
    approval_id: str | None = Field(default=None, max_length=64)
    policy_version: str | None = Field(default=None, max_length=64)
    declared_principal_id: str | None = Field(default=None, max_length=128)


class ExecuteResponse(BaseModel):
    """Outcome of PEP tool execution."""

    model_config = ConfigDict(extra="forbid")

    status: str
    result: Any | None = None
    reason_code: str
    approval_id: str | None = None
    execution_time_ms: float = 0.0


class CreateApprovalRequest(BaseModel):
    """Payload to create an authorization review request."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(min_length=1, max_length=128)
    action_name: str = Field(min_length=1, max_length=256)
    argument_hash: str = Field(min_length=64, max_length=64)
    policy_version: str = Field(default="1.0.0", max_length=64)
    ttl_seconds: int | None = Field(default=300, ge=10, le=86400)


class ApprovalResponse(BaseModel):
    """Details of a human approval record."""

    model_config = ConfigDict(extra="forbid")

    approval_id: str
    request_id: str
    principal_id: str
    tool_name: str
    action_name: str
    argument_hash: str
    policy_version: str
    status: str
    created_at: datetime
    expires_at: datetime
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    consumed_at: datetime | None = None


class ApprovalListResponse(BaseModel):
    """Paginated list of approval records with access control bounds."""

    model_config = ConfigDict(extra="forbid")

    approvals: list[ApprovalResponse]
    count: int
    limit: int
    offset: int


class ApproveActionRequest(BaseModel):
    """Payload for approving a pending authorization request."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default="Approved by supervisor", max_length=500)


class RejectActionRequest(BaseModel):
    """Payload for rejecting a pending authorization request."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="Supervisor rejected action", max_length=500)


class AuditEventResponse(BaseModel):
    """Structured audit log entry."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    request_id: str
    event_type: str
    timestamp: datetime
    component: str
    decision: str | None = None
    policy_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditQueryResponse(BaseModel):
    """Paginated audit query results."""

    model_config = ConfigDict(extra="forbid")

    events: list[AuditEventResponse]
    count: int
    limit: int
    offset: int


class BenchmarkSummaryResponse(BaseModel):
    """High-level summary of starter benchmark suite."""

    model_config = ConfigDict(extra="forbid")

    dataset_name: str
    dataset_version: str
    total_cases: int
    categories: list[str]


class HybridBenchmarkSummaryResponse(BaseModel):
    """Metadata regarding supported hybrid evaluation providers, budgets, and capabilities."""

    model_config = ConfigDict(extra="forbid")

    supported_providers: list[str]
    default_model: str
    supported_models: list[str]
    default_budget_ceiling_usd: float
    max_budget_ceiling_usd: float
    pricing_rates: dict[str, dict[str, float]]
    features: list[str]


class BenchmarkRunResponse(BaseModel):
    """PromptProbe benchmark execution results."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    timestamp: datetime
    total_cases: int
    passed_cases: int
    failed_cases: int
    accuracy: float
    scenario_pass_rate: float | None = None
    metrics: dict[str, Any]


class ErrorResponse(BaseModel):
    """Uniform error response structure."""

    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str | None = None
    request_id: str | None = None
