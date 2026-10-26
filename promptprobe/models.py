"""Typed domain models and schemas for PromptProbe evaluation benchmarks."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinelllm.contracts.decision import Decision
from sentinelllm.contracts.provenance import ContentProvenance, TrustClassification
from sentinelllm.policy.principal import AnonymousPrincipal, AuthenticatedPrincipal


class EvaluationCategory(StrEnum):
    """Functional category classification for benchmark cases."""

    BENIGN_USER = "benign_user"
    DIRECT_INJECTION = "direct_injection"
    INSTRUCTION_EXTRACTION = "instruction_extraction"
    CANARY_LEAK = "canary_leak"
    INDIRECT_INJECTION_RAG = "indirect_injection_rag"
    INDIRECT_INJECTION_TOOL = "indirect_injection_tool"
    BENIGN_SECURITY_DISCUSSION = "benign_security_discussion"
    TOOL_AUTHORIZED = "tool_authorized"
    TOOL_UNAUTHORIZED = "tool_unauthorized"
    TOOL_REQUIRES_APPROVAL = "tool_requires_approval"
    TOOL_UNKNOWN = "tool_unknown"
    TOOL_MALFORMED_ARGS = "tool_malformed_args"


class EvaluationCase(BaseModel):
    """A single synthetic test case within a PromptProbe benchmark dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    category: EvaluationCategory
    description: str = Field(min_length=1)

    # Scanned content payload
    content: str
    provenance: ContentProvenance = ContentProvenance.USER_MESSAGE
    trust_classification: TrustClassification = TrustClassification.USER_INPUT

    # Action parameters (for tool authorization and PEP evaluation)
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    principal_id: str | None = None
    principal_permissions: list[str] = Field(default_factory=list)
    principal_roles: list[str] = Field(default_factory=list)

    # Expected detection outcomes
    expected_finding: bool = False
    expected_finding_category: str | None = None

    # Expected policy / PEP enforcement outcomes
    expected_decision: Decision | None = None
    expected_status: str | None = None  # "executed", "denied", "pending_approval", "error"
    expected_reason_code: str | None = None

    explanation: str = ""

    @field_validator("expected_decision", mode="before")
    @classmethod
    def _normalize_decision(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v

    def get_principal(self) -> AuthenticatedPrincipal | None:
        """Construct the AuthenticatedPrincipal representing the case caller."""
        if self.principal_id is None:
            return AnonymousPrincipal()
        return AuthenticatedPrincipal(
            principal_id=self.principal_id,
            permissions=frozenset(self.principal_permissions),
            roles=frozenset(self.principal_roles),
            is_authenticated=True,
        )


class DatasetContainer(BaseModel):
    """Container validating a versioned PromptProbe benchmark dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    disclaimer: str = Field(min_length=1)
    cases: list[EvaluationCase] = Field(min_length=1)

    @field_validator("cases")
    @classmethod
    def _assert_unique_case_ids(cls, v: list[EvaluationCase]) -> list[EvaluationCase]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for c in v:
            if c.case_id in seen:
                duplicates.add(c.case_id)
            seen.add(c.case_id)
        if duplicates:
            raise ValueError(f"Duplicate case_id(s) detected in dataset: {sorted(duplicates)}")
        return v


class CaseEvaluationResult(BaseModel):
    """Detailed result for an individual evaluated case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    category: EvaluationCategory
    success: bool
    actual_finding: bool
    actual_finding_category: str | None = None
    actual_decision: str | None = None
    actual_status: str | None = None
    actual_reason_code: str | None = None
    error_message: str | None = None


class ConfusionMatrix(BaseModel):
    """Detection evaluation confusion matrix and classification metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    total_samples: int = 0
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    accuracy: float = 0.0
    false_positive_rate: float | None = None
    notes: str = ""


class EnforcementMetrics(BaseModel):
    """Authorization and action-level policy enforcement metrics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_action_cases: int = 0
    unauthorized_executions: int = 0  # CRITICAL SAFETY METRIC: must remain 0
    correctly_denied: int = 0
    correctly_permitted: int = 0
    correctly_held_for_approval: int = 0
    invalid_or_unknown_prevented: int = 0
    enforcement_accuracy: float | None = None
    notes: str = ""


class BenchmarkReport(BaseModel):
    """Machine-readable summary artifact of a completed PromptProbe benchmark run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = "PromptProbe Benchmark"
    dataset_name: str
    dataset_version: str
    package_version: str
    policy_version: str
    configuration_name: str
    run_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    seed: int = 42
    total_cases: int
    passed_cases: int
    failed_cases: int
    detector_metrics: ConfusionMatrix
    enforcement_metrics: EnforcementMetrics
    failures: list[dict[str, Any]] = Field(default_factory=list)
    case_results: list[CaseEvaluationResult] = Field(default_factory=list)
