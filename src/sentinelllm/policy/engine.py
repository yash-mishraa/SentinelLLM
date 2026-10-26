"""Deterministic Policy Decision Point (PDP) engine and rule configuration."""

from fnmatch import fnmatch
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from sentinelllm.contracts.decision import Decision, SecurityDecision, Severity
from sentinelllm.policy.models import AuthorizationRequest

# Standardized machine-readable reason codes
REASON_ALLOW_EXPLICIT: Final[str] = "ALLOW_EXPLICIT_PERMISSION"
REASON_DENY_MISSING_IDENTITY: Final[str] = "DENY_MISSING_IDENTITY"
REASON_DENY_INSUFFICIENT_PERMISSION: Final[str] = "DENY_INSUFFICIENT_PERMISSION"
REASON_DENY_HIGH_RISK_FINDINGS: Final[str] = "DENY_HIGH_RISK_FINDINGS"
REASON_DENY_UNKNOWN_TOOL: Final[str] = "DENY_UNKNOWN_TOOL"
REASON_DENY_INVALID_ARGUMENTS: Final[str] = "DENY_INVALID_ARGUMENTS"
REASON_REVIEW_APPROVAL_REQUIRED: Final[str] = "REVIEW_APPROVAL_REQUIRED"
REASON_DENY_MALFORMED_REQUEST: Final[str] = "DENY_MALFORMED_REQUEST"
REASON_DENY_POLICY_UNAVAILABLE: Final[str] = "DENY_POLICY_UNAVAILABLE"
REASON_DENY_DEFAULT_CLOSED: Final[str] = "DENY_DEFAULT_CLOSED"


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

        Precedence order:
        1. Malformed request check -> BLOCK (DENY_MALFORMED_REQUEST)
        2. Authenticated identity check -> BLOCK (DENY_MISSING_IDENTITY)
        3. High-risk finding containment rule -> BLOCK (DENY_HIGH_RISK_FINDINGS)
        4. Matching rules evaluated in sequence:
           a. Explicit BLOCK -> BLOCK
           b. Approval required -> REVIEW
           c. Explicit ALLOW -> ALLOW (only if permissions & roles satisfied)
        5. Default fail-closed fallback -> BLOCK (DENY_INSUFFICIENT_PERMISSION)
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

        # 2. High-risk detector containment
        # Critical findings (canary leak) or high-severity injection findings block execution
        has_critical_findings = any(f.severity == Severity.CRITICAL for f in request.findings)
        has_high_injection = any(
            f.severity == Severity.HIGH and f.category == "prompt_injection"
            for f in request.findings
        )
        if has_critical_findings or has_high_injection:
            return SecurityDecision(
                decision=Decision.BLOCK,
                reason=REASON_DENY_HIGH_RISK_FINDINGS,
                policy_version=self.policy_version,
                findings=request.findings,
            )

        # 3. Rule evaluation
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

            # Check approval requirements
            if rule.requires_approval or rule.effect == Decision.REVIEW:
                return SecurityDecision(
                    decision=Decision.REVIEW,
                    reason=rule.reason_code,
                    policy_version=self.policy_version,
                    findings=request.findings,
                    metadata={"rule_id": rule.rule_id, "explanation": rule.explanation},
                )

            if rule.effect == Decision.BLOCK:
                return SecurityDecision(
                    decision=Decision.BLOCK,
                    reason=rule.reason_code,
                    policy_version=self.policy_version,
                    findings=request.findings,
                    metadata={"rule_id": rule.rule_id, "explanation": rule.explanation},
                )

            if rule.effect == Decision.ALLOW:
                return SecurityDecision(
                    decision=Decision.ALLOW,
                    reason=rule.reason_code,
                    policy_version=self.policy_version,
                    findings=request.findings,
                    metadata={"rule_id": rule.rule_id, "explanation": rule.explanation},
                )

        # 4. Default fail-closed fallback
        return SecurityDecision(
            decision=self._config.default_decision,
            reason=REASON_DENY_INSUFFICIENT_PERMISSION,
            policy_version=self.policy_version,
            findings=request.findings,
        )
