"""Deterministic Policy Decision Point (PDP) engine and rule configuration."""

from fnmatch import fnmatch
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinelllm.contracts.decision import Decision, SecurityDecision, Severity
from sentinelllm.policy.models import AuthorizationRequest

# Standardized machine-readable reason codes
REASON_ALLOW_EXPLICIT: Final[str] = "ALLOW_EXPLICIT_PERMISSION"
REASON_DENY_MISSING_IDENTITY: Final[str] = "DENY_MISSING_IDENTITY"
REASON_DENY_INSUFFICIENT_PERMISSION: Final[str] = "DENY_INSUFFICIENT_PERMISSION"
REASON_DENY_HIGH_RISK_FINDINGS: Final[str] = "DENY_HIGH_RISK_FINDINGS"
REASON_REVIEW_DETECTOR_FINDINGS: Final[str] = "REVIEW_DETECTOR_FINDINGS"
REASON_DENY_UNKNOWN_TOOL: Final[str] = "DENY_UNKNOWN_TOOL"
REASON_DENY_INVALID_ARGUMENTS: Final[str] = "DENY_INVALID_ARGUMENTS"
REASON_REVIEW_APPROVAL_REQUIRED: Final[str] = "REVIEW_APPROVAL_REQUIRED"
REASON_DENY_MALFORMED_REQUEST: Final[str] = "DENY_MALFORMED_REQUEST"
REASON_DENY_POLICY_UNAVAILABLE: Final[str] = "DENY_POLICY_UNAVAILABLE"
REASON_DENY_DEFAULT_CLOSED: Final[str] = "DENY_DEFAULT_CLOSED"

# Approval workflow reason codes
REASON_DENY_APPROVAL_UNKNOWN: Final[str] = "DENY_APPROVAL_UNKNOWN"
REASON_DENY_APPROVAL_PENDING: Final[str] = "DENY_APPROVAL_PENDING"
REASON_DENY_APPROVAL_REJECTED: Final[str] = "DENY_APPROVAL_REJECTED"
REASON_DENY_APPROVAL_EXPIRED: Final[str] = "DENY_APPROVAL_EXPIRED"
REASON_DENY_APPROVAL_ALREADY_CONSUMED: Final[str] = "DENY_APPROVAL_ALREADY_CONSUMED"
REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH: Final[str] = "DENY_APPROVAL_PRINCIPAL_MISMATCH"
REASON_DENY_APPROVAL_TOOL_MISMATCH: Final[str] = "DENY_APPROVAL_TOOL_MISMATCH"
REASON_DENY_APPROVAL_ACTION_MISMATCH: Final[str] = "DENY_APPROVAL_ACTION_MISMATCH"
REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH: Final[str] = "DENY_APPROVAL_ARGUMENTS_MISMATCH"
REASON_DENY_APPROVAL_POLICY_MISMATCH: Final[str] = "DENY_APPROVAL_POLICY_MISMATCH"
REASON_DENY_APPROVAL_INVALID: Final[str] = "DENY_APPROVAL_INVALID"


class PolicyRule(BaseModel):
    """An explicit, deterministic rule evaluated by the policy engine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    action_pattern: str = Field(min_length=1)
    resource_pattern: str = Field(min_length=1)
    required_permissions: frozenset[str] = Field(default_factory=frozenset)
    required_roles: frozenset[str] = Field(default_factory=frozenset)
    effect: Decision = Decision.ALLOW
    requires_approval: bool = False
    reason_code: str = REASON_ALLOW_EXPLICIT
    explanation: str = ""

    def matches(self, action: str, resource: str) -> bool:
        """Check if this rule matches the requested action and resource."""
        return fnmatch(action, self.action_pattern) and fnmatch(resource, self.resource_pattern)


class PolicyConfig(BaseModel):
    """Structured configuration container for policy rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = "1.0.0"
    rules: tuple[PolicyRule, ...] = Field(default_factory=tuple)
    default_decision: Decision = Decision.BLOCK
    default_reason_code: str = REASON_DENY_DEFAULT_CLOSED
    critical_findings_effect: Decision = Decision.BLOCK
    high_findings_effect: Decision = Decision.BLOCK

    @field_validator("critical_findings_effect", "high_findings_effect")
    @classmethod
    def _validate_finding_effects(cls, v: Decision) -> Decision:
        if v not in (Decision.BLOCK, Decision.REVIEW):
            raise ValueError(
                f"Detector findings cannot produce effect {v}; only BLOCK or REVIEW permitted."
            )
        return v


# Standard baseline policy rules for simulated tools
DEFAULT_POLICY_RULES: Final[tuple[PolicyRule, ...]] = (
    PolicyRule(
        rule_id="RULE_DOCS_SEARCH",
        action_pattern="tools:execute:search_documents",
        resource_pattern="documents",
        required_permissions=frozenset({"documents:search"}),
        effect=Decision.ALLOW,
        reason_code=REASON_ALLOW_EXPLICIT,
        explanation="Permitted read-only document search for authorized callers.",
    ),
    PolicyRule(
        rule_id="RULE_CUSTOMER_READ",
        action_pattern="tools:execute:read_customer_record",
        resource_pattern="customer_records",
        required_permissions=frozenset({"records:read"}),
        effect=Decision.ALLOW,
        reason_code=REASON_ALLOW_EXPLICIT,
        explanation="Permitted single customer record read for authorized callers.",
    ),
    PolicyRule(
        rule_id="RULE_CUSTOMER_EXPORT",
        action_pattern="tools:execute:export_customer_records",
        resource_pattern="customer_records",
        required_permissions=frozenset({"records:export"}),
        effect=Decision.REVIEW,
        requires_approval=True,
        reason_code=REASON_REVIEW_APPROVAL_REQUIRED,
        explanation="Sensitive export action requires human supervisor approval.",
    ),
)


class PolicyDecisionPoint:
    """Deterministic Policy Decision Point (PDP).

    Evaluates AuthorizationRequests against explicit PolicyRules, enforcing
    fail-closed defaults, least privilege, and strict separation between
    detector observations and enforcement decisions.
    """

    def __init__(self, config: PolicyConfig | None = None) -> None:
        if config is None:
            self._config = PolicyConfig(rules=DEFAULT_POLICY_RULES)
        else:
            self._config = config

    @property
    def policy_version(self) -> str:
        return self._config.policy_version

    def evaluate(self, request: AuthorizationRequest) -> SecurityDecision:
        """Evaluate an authorization request and return an authoritative SecurityDecision.

        Precedence order (fail-closed):
        1. Malformed request check -> BLOCK (DENY_MALFORMED_REQUEST)
        2. Authenticated identity check -> BLOCK (DENY_MISSING_IDENTITY)
        3. Critical finding containment -> BLOCK (critical_findings_effect)
        4. Rule matching & permission authorization:
           a. Explicit BLOCK rule -> BLOCK
           b. Match allow/review rule -> proceed to detector check
           c. No matching rule or missing permissions -> BLOCK (DENY_INSUFFICIENT_PERMISSION)
        5. Permitted action detector evaluation:
           a. High-severity finding with BLOCK policy -> BLOCK (DENY_HIGH_RISK_FINDINGS)
           b. High-severity finding with REVIEW policy -> REVIEW (REVIEW_DETECTOR_FINDINGS)
        6. Rule effect:
           a. Approval required / REVIEW rule -> REVIEW
           b. Explicit ALLOW rule -> ALLOW
        """
        if not isinstance(request, AuthorizationRequest):
            return SecurityDecision(  # type: ignore[unreachable]
                decision=Decision.BLOCK,
                reason=REASON_DENY_MALFORMED_REQUEST,
                policy_version=self.policy_version,
            )

        # 1. Identity validation (fail closed on missing / unauthenticated principal)
        principal = request.principal
        if principal is None or not principal.is_authenticated:
            return SecurityDecision(
                decision=Decision.BLOCK,
                reason=REASON_DENY_MISSING_IDENTITY,
                policy_version=self.policy_version,
                findings=request.findings,
            )

        # 2. Critical detector containment (unconditional containment)
        has_critical = any(f.severity == Severity.CRITICAL for f in request.findings)
        if has_critical:
            return SecurityDecision(
                decision=self._config.critical_findings_effect,
                reason=REASON_DENY_HIGH_RISK_FINDINGS,
                policy_version=self.policy_version,
                findings=request.findings,
            )

        # 3. Rule matching & authorization
        matched_rule: PolicyRule | None = None
        for rule in self._config.rules:
            if not rule.matches(request.action, request.resource):
                continue

            # Verify required permissions
            missing_permissions = rule.required_permissions - principal.permissions
            if missing_permissions and "*" not in principal.permissions:
                continue

            # Verify required roles
            missing_roles = rule.required_roles - principal.roles
            if missing_roles and "admin" not in principal.roles:
                continue

            # Explicit BLOCK terminates immediately
            if rule.effect == Decision.BLOCK:
                return SecurityDecision(
                    decision=Decision.BLOCK,
                    reason=rule.reason_code,
                    policy_version=self.policy_version,
                    findings=request.findings,
                    metadata={"rule_id": rule.rule_id, "explanation": rule.explanation},
                )

            matched_rule = rule
            break

        if matched_rule is None:
            # Default fail-closed fallback
            return SecurityDecision(
                decision=self._config.default_decision,
                reason=REASON_DENY_INSUFFICIENT_PERMISSION,
                policy_version=self.policy_version,
                findings=request.findings,
            )

        # 4. Detector-driven policy evaluation for authorized actions
        has_high_findings = any(f.severity == Severity.HIGH for f in request.findings)
        if has_high_findings:
            if self._config.high_findings_effect == Decision.BLOCK:
                return SecurityDecision(
                    decision=Decision.BLOCK,
                    reason=REASON_DENY_HIGH_RISK_FINDINGS,
                    policy_version=self.policy_version,
                    findings=request.findings,
                )
            if self._config.high_findings_effect == Decision.REVIEW:
                return SecurityDecision(
                    decision=Decision.REVIEW,
                    reason=REASON_REVIEW_DETECTOR_FINDINGS,
                    policy_version=self.policy_version,
                    findings=request.findings,
                    metadata={"escalated_from": matched_rule.rule_id},
                )

        # 5. Rule execution effect
        if matched_rule.requires_approval or matched_rule.effect == Decision.REVIEW:
            return SecurityDecision(
                decision=Decision.REVIEW,
                reason=matched_rule.reason_code,
                policy_version=self.policy_version,
                findings=request.findings,
                metadata={"rule_id": matched_rule.rule_id, "explanation": matched_rule.explanation},
            )

        if matched_rule.effect == Decision.ALLOW:
            return SecurityDecision(
                decision=Decision.ALLOW,
                reason=matched_rule.reason_code,
                policy_version=self.policy_version,
                findings=request.findings,
                metadata={"rule_id": matched_rule.rule_id, "explanation": matched_rule.explanation},
            )

        return SecurityDecision(
            decision=self._config.default_decision,
            reason=REASON_DENY_INSUFFICIENT_PERMISSION,
            policy_version=self.policy_version,
            findings=request.findings,
        )
