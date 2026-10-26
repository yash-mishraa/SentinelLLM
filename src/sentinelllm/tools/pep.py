"""Policy Enforcement Point (PEP) governing controlled tool execution."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sentinelllm.contracts.audit import AuditEvent
from sentinelllm.contracts.decision import Decision, SecurityDecision, SecurityFinding
from sentinelllm.contracts.messages import ToolOutput
from sentinelllm.contracts.provenance import ContentProvenance, TrustClassification
from sentinelllm.policy.engine import (
    REASON_DENY_INVALID_ARGUMENTS,
    REASON_DENY_UNKNOWN_TOOL,
    PolicyDecisionPoint,
)
from sentinelllm.policy.models import AuthorizationRequest
from sentinelllm.policy.principal import AuthenticatedPrincipal
from sentinelllm.tools.registry import ToolRegistry


class ToolExecutionResult(BaseModel):
    """Structured outcome returned by the Policy Enforcement Point."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str  # "executed", "denied", "pending_approval", "error"
    tool_name: str
    decision: SecurityDecision | None = None
    reason_code: str
    output: ToolOutput | None = None
    audit_events: tuple[AuditEvent, ...] = Field(default_factory=tuple)
    error_message: str | None = None


class PolicyEnforcementPoint:
    """Action-level authorization boundary for tool execution.

    Intercepts all proposed tool invocations out-of-band, validates argument
    schemas, queries the Policy Decision Point (PDP), and executes tools only
    when explicitly authorized.
    """

    def __init__(
        self,
        pdp: PolicyDecisionPoint | None = None,
        registry: ToolRegistry | None = None,
        component_name: str = "policy_enforcement_point",
    ) -> None:
        self.pdp = pdp if pdp is not None else PolicyDecisionPoint()
        self.registry = registry if registry is not None else ToolRegistry.create_default_registry()
        self.component_name = component_name

    def invoke(
        self,
        tool_name: str,
        raw_arguments: dict[str, Any],
        principal: AuthenticatedPrincipal | None = None,
        context_trust: TrustClassification = TrustClassification.UNTRUSTED_CONTEXT,
        findings: tuple[SecurityFinding, ...] = (),
        request_id: str | None = None,
    ) -> ToolExecutionResult:
        """Evaluate authorization and execute tool if permitted.

        Args:
            tool_name: Name of the tool requested.
            raw_arguments: Dictionary of arguments supplied for the tool.
            principal: Authenticated caller identity.
            context_trust: Trust classification of the triggering context.
            findings: Security findings associated with the request context.
            request_id: Optional correlation request ID.

        Returns:
            ToolExecutionResult detailing execution outcome, decision, and audit trails.
        """
        audit_events: list[AuditEvent] = []
        effective_req_id = request_id if request_id is not None else "unassigned"

        # 1. Tool existence check
        spec = self.registry.get_spec(tool_name)
        if spec is None:
            denied_event = AuditEvent(
                request_id=effective_req_id,
                event_type="tool.rejected",
                component=self.component_name,
                decision=Decision.BLOCK,
                metadata={
                    "tool_name": tool_name,
                    "reason_code": REASON_DENY_UNKNOWN_TOOL,
                },
            )
            audit_events.append(denied_event)
            return ToolExecutionResult(
                status="denied",
                tool_name=tool_name,
                reason_code=REASON_DENY_UNKNOWN_TOOL,
                audit_events=tuple(audit_events),
                error_message=f"Tool '{tool_name}' is not registered in the tool registry.",
            )

        # 2. Argument schema validation
        try:
            validated_args = spec.argument_schema.model_validate(raw_arguments)
        except ValidationError as err:
            invalid_event = AuditEvent(
                request_id=effective_req_id,
                event_type="tool.rejected",
                component=self.component_name,
                decision=Decision.BLOCK,
                metadata={
                    "tool_name": tool_name,
                    "reason_code": REASON_DENY_INVALID_ARGUMENTS,
                },
            )
            audit_events.append(invalid_event)
            return ToolExecutionResult(
                status="denied",
                tool_name=tool_name,
                reason_code=REASON_DENY_INVALID_ARGUMENTS,
                audit_events=tuple(audit_events),
                error_message=f"Invalid arguments for tool '{tool_name}': {err.errors()}",
            )

        # 3. Request authorization decision from PDP
        auth_request = AuthorizationRequest(
            principal=principal,
            action=spec.action_identifier,
            resource=spec.resource_classification,
            context_trust=context_trust,
            findings=findings,
            policy_version=self.pdp.policy_version,
            request_id=effective_req_id,
            metadata={"tool_name": tool_name},
        )
        decision = self.pdp.evaluate(auth_request)

        # 4. Enforce decision outcome
        if decision.decision == Decision.BLOCK:
            block_event = AuditEvent(
                request_id=effective_req_id,
                event_type="tool.rejected",
                component=self.component_name,
                decision=Decision.BLOCK,
                policy_version=decision.policy_version,
                metadata={
                    "tool_name": tool_name,
                    "reason_code": decision.reason,
                    "principal_id": principal.principal_id if principal else "anonymous",
                },
            )
            audit_events.append(block_event)
            return ToolExecutionResult(
                status="denied",
                tool_name=tool_name,
                decision=decision,
                reason_code=decision.reason,
                audit_events=tuple(audit_events),
            )

        if decision.decision == Decision.REVIEW:
            review_event = AuditEvent(
                request_id=effective_req_id,
                event_type="tool.review_required",
                component=self.component_name,
                decision=Decision.REVIEW,
                policy_version=decision.policy_version,
                metadata={
                    "tool_name": tool_name,
                    "reason_code": decision.reason,
                    "principal_id": principal.principal_id if principal else "anonymous",
                },
            )
            audit_events.append(review_event)
            return ToolExecutionResult(
                status="pending_approval",
                tool_name=tool_name,
                decision=decision,
                reason_code=decision.reason,
                audit_events=tuple(audit_events),
            )

        # 5. Execute authorized tool
        try:
            raw_output = self.registry.execute(tool_name, validated_args)
            tool_output = ToolOutput(
                content=raw_output,
                tool_name=tool_name,
                provenance=ContentProvenance.EXTERNAL_TOOL,
                trust_classification=TrustClassification.UNTRUSTED_CONTEXT,
            )
            executed_event = AuditEvent(
                request_id=effective_req_id,
                event_type="tool.executed",
                component=self.component_name,
                decision=Decision.ALLOW,
                policy_version=decision.policy_version,
                metadata={
                    "tool_name": tool_name,
                    "reason_code": decision.reason,
                    "principal_id": principal.principal_id if principal else "anonymous",
                },
            )
            audit_events.append(executed_event)
            return ToolExecutionResult(
                status="executed",
                tool_name=tool_name,
                decision=decision,
                reason_code=decision.reason,
                output=tool_output,
                audit_events=tuple(audit_events),
            )
        except Exception as ex:
            error_event = AuditEvent(
                request_id=effective_req_id,
                event_type="tool.error",
                component=self.component_name,
                decision=Decision.BLOCK,
                metadata={
                    "tool_name": tool_name,
                    "error": type(ex).__name__,
                },
            )
            audit_events.append(error_event)
            return ToolExecutionResult(
                status="error",
                tool_name=tool_name,
                decision=decision,
                reason_code="EXECUTION_ERROR",
                audit_events=tuple(audit_events),
                error_message=str(ex),
            )
