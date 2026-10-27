"""Data models and metrics schemas for PromptProbe hybrid evaluation."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ModelExecutionStatus(StrEnum):
    """Execution disposition of an evaluation case with respect to the LLM adapter."""

    BLOCKED_BY_GATEWAY = "BLOCKED_BY_GATEWAY"  # Gateway intercepted attack; zero tokens dispatched
    DISPATCHED = "DISPATCHED"  # Gateway permitted input; dispatched to model
    UNPROTECTED_DISPATCHED = "UNPROTECTED_DISPATCHED"  # Baseline run without gateway protection
    PROVIDER_FAILURE = "PROVIDER_FAILURE"  # Network error, timeout, 401, or 429 from provider
    SKIPPED_BUDGET = "SKIPPED_BUDGET"  # Terminated early to prevent exceeding budget


class HybridCaseResult(BaseModel):
    """Outcome of evaluating an individual case through SentinelLLM and the model adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    category: str
    is_adversarial: bool
    is_action_case: bool = False
    gateway_decision: str  # "BLOCK" or "ALLOW"
    gateway_finding_detected: bool
    gateway_reason_code: str | None = None
    gateway_latency_ms: float = 0.0

    model_status: ModelExecutionStatus
    model_response_snippet: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_saved_by_gateway: int = 0
    cost_usd: float = 0.0
    is_cost_estimated: bool = True
    model_latency_ms: float = 0.0
    error_message: str | None = None


class HybridMetrics(BaseModel):
    """Separated metric aggregates for gateway defense accuracy and model token/cost consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_cases: int
    content_cases: int = 0
    action_cases: int = 0

    # Content Gateway Detection Metrics (Content Classification)
    attacks_blocked_by_gateway: int  # True positives
    attacks_reaching_model: int  # False negatives
    benign_dispatched: int  # True negatives
    benign_blocked_by_gateway: int  # False positives

    gateway_precision: float | None = None
    gateway_recall: float | None = None
    gateway_f1: float | None = None
    gateway_accuracy: float = 0.0

    # Action Authorization Metrics (Tool Control)
    actions_enforced_correctly: int = 0
    unauthorized_actions_prevented: int = 0

    # Resource & Cost Metrics
    total_tokens_consumed: int = 0
    tokens_saved_by_gateway: int = 0
    total_cost_usd: float = 0.0
    is_cost_estimated: bool = True
    provider_failures: int = 0
    budget_exhausted: bool = False


class HybridBenchmarkReport(BaseModel):
    """Comprehensive hybrid evaluation report separating gateway security from model telemetry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str
    dataset_name: str
    dataset_version: str
    provider: str
    model: str
    is_live: bool
    run_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    budget_summary: dict[str, Any]
    metrics: HybridMetrics
    case_results: list[HybridCaseResult]
