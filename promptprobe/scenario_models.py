"""Typed schemas and models for PromptProbe multi-step adversarial scenario evaluations."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinelllm.contracts.provenance import ContentProvenance, TrustClassification
from sentinelllm.policy.principal import AnonymousPrincipal, AuthenticatedPrincipal


class ScenarioStepType(StrEnum):
    """Categorical step type within an ordered scenario trace."""

    USER_MESSAGE = "user_message"
    RETRIEVED_CHUNK = "retrieved_chunk"
    TOOL_OUTPUT = "tool_output"
    TOOL_ACTION = "tool_action"
    APPROVAL_DECISION = "approval_decision"


class ScenarioStep(BaseModel):
    """A discrete, ordered step in a multi-step security scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str = Field(min_length=1)
    step_type: ScenarioStepType
    description: str = Field(default="")

    # Content attributes (for user_message, retrieved_chunk, tool_output)
    content: str | None = None
    source: str | None = None
    provenance: ContentProvenance | None = None
    trust_classification: TrustClassification | None = None
    chunk_id: str | None = None

    # Tool invocation attributes (for tool_action)
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    principal_id: str | None = None
    principal_permissions: list[str] = Field(default_factory=list)
    principal_roles: list[str] = Field(default_factory=list)
    use_prior_approval: bool = False
    tampered_arguments: dict[str, Any] | None = None

    # Approval attributes (for approval_decision)
    approver_id: str | None = None
    approver_permissions: list[str] = Field(default_factory=list)
    approver_roles: list[str] = Field(default_factory=list)
    approval_decision: str | None = None  # "approve" or "reject"

    # Expected outcomes
    expected_finding: bool | None = None
    expected_finding_category: str | None = None
    # Expected status: "executed", "denied", "pending_approval", "approved", "rejected"
    expected_status: str | None = None
    expected_reason_code: str | None = None
    explanation: str = Field(default="")

    def get_principal(self) -> AuthenticatedPrincipal:
        """Construct the AuthenticatedPrincipal representing the action caller."""
        if self.principal_id is None:
            return AnonymousPrincipal()
        return AuthenticatedPrincipal(
            principal_id=self.principal_id,
            permissions=frozenset(self.principal_permissions),
            roles=frozenset(self.principal_roles),
            is_authenticated=True,
        )

    def get_approver(self) -> AuthenticatedPrincipal:
        """Construct the AuthenticatedPrincipal representing the approver."""
        return AuthenticatedPrincipal(
            principal_id=self.approver_id if self.approver_id else "approver_default",
            permissions=frozenset(
                self.approver_permissions if self.approver_permissions else ["approvals:manage"]
            ),
            roles=frozenset(self.approver_roles if self.approver_roles else ["admin"]),
            is_authenticated=True,
        )


class SecurityScenario(BaseModel):
    """An end-to-end multi-step scenario trace evaluating defense invariants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    steps: list[ScenarioStep] = Field(min_length=1)


class ScenarioDatasetContainer(BaseModel):
    """Container validating a versioned collection of multi-step scenarios."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    disclaimer: str = Field(min_length=1)
    scenarios: list[SecurityScenario] = Field(min_length=1)

    @field_validator("scenarios")
    @classmethod
    def _assert_unique_scenario_ids(cls, v: list[SecurityScenario]) -> list[SecurityScenario]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for s in v:
            if s.scenario_id in seen:
                duplicates.add(s.scenario_id)
            seen.add(s.scenario_id)
        if duplicates:
            raise ValueError(f"Duplicate scenario_id(s) detected: {sorted(duplicates)}")
        return v


class ScenarioStepResult(BaseModel):
    """Individual execution result for a single step in a scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: str
    step_type: ScenarioStepType
    success: bool
    actual_finding: bool = False
    actual_finding_category: str | None = None
    actual_status: str | None = None
    actual_reason_code: str | None = None
    unauthorized_execution: bool = False
    provenance_violation: bool = False
    error_message: str | None = None


class ScenarioResult(BaseModel):
    """Overall outcome of a multi-step scenario trace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str
    category: str
    title: str
    passed: bool
    total_steps: int
    step_results: list[ScenarioStepResult] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)


class ScenarioMetrics(BaseModel):
    """Scenario-level and enforcement metrics computed across evaluated traces."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_scenarios: int = 0
    passed_scenarios: int = 0
    failed_scenarios: int = 0
    total_steps_evaluated: int = 0
    unauthorized_executions: int = 0  # CRITICAL SAFETY INVARIANT: must remain 0
    correctly_blocked_actions: int = 0
    actions_safely_held_for_approval: int = 0
    provenance_violations: int = 0
    unexpected_executions: int = 0
    unexpected_denials: int = 0
    scenario_success_rate: float = 0.0
    notes: str = ""


class ScenarioBenchmarkReport(BaseModel):
    """Summary report artifact for multi-step scenario evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = "PromptProbe Multi-Step Scenario Evaluation"
    dataset_name: str
    dataset_version: str
    package_version: str
    policy_version: str
    configuration_name: str
    run_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    seed: int = 42
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    metrics: ScenarioMetrics
    failures: list[dict[str, Any]] = Field(default_factory=list)
    scenario_results: list[ScenarioResult] = Field(default_factory=list)
