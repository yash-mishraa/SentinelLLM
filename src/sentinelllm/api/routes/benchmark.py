"""Benchmark inspection and execution endpoints."""

import threading
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from sentinelllm.api.dependencies import (
    check_rate_limit,
    get_current_principal,
    get_db_session,
    require_role,
)
from sentinelllm.api.schemas import (
    BenchmarkRunResponse,
    BenchmarkSummaryResponse,
    HybridBenchmarkSummaryResponse,
)
from sentinelllm.db.models import BenchmarkRunModel
from sentinelllm.policy.principal import AuthenticatedPrincipal

router = APIRouter(prefix="/benchmark", tags=["Benchmark & Evaluation"])

# Global concurrency guard to prevent resource exhaustion from parallel benchmark runs
_BENCHMARK_RUN_LOCK = threading.Lock()


@router.get(
    "/summary",
    response_model=BenchmarkSummaryResponse,
    summary="Benchmark Suite Summary",
    description="Returns metadata and category coverage for the starter adversarial benchmark.",
    dependencies=[Depends(check_rate_limit)],
)
def get_benchmark_summary(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> BenchmarkSummaryResponse:
    """Retrieve metadata about the pre-packaged PromptProbe adversarial benchmark."""
    from promptprobe.dataset import load_dataset

    dataset = load_dataset()
    categories = sorted({c.category.value for c in dataset.cases})

    return BenchmarkSummaryResponse(
        dataset_name=dataset.dataset_name,
        dataset_version=dataset.version,
        total_cases=len(dataset.cases),
        categories=categories,
    )


@router.get(
    "/hybrid/summary",
    response_model=HybridBenchmarkSummaryResponse,
    summary="Hybrid Evaluation Capabilities",
    description=(
        "Returns metadata regarding supported live/synthetic LLM providers, "
        "pricing rates, and budget ceilings."
    ),
    dependencies=[Depends(check_rate_limit)],
)
def get_hybrid_benchmark_summary(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> HybridBenchmarkSummaryResponse:
    """Retrieve capabilities and cost bounds for PromptProbe hybrid evaluation."""
    from sentinelllm.adapters import (
        DEFAULT_BUDGET_CEILING_USD,
        MAX_ALLOWED_BUDGET_CEILING_USD,
        MODEL_PRICING_RATES,
    )

    supported_models = list(MODEL_PRICING_RATES.keys())
    rates = {
        model: {
            "prompt_per_million": r[0],
            "completion_per_million": r[1],
        }
        for model, r in MODEL_PRICING_RATES.items()
    }

    return HybridBenchmarkSummaryResponse(
        supported_providers=["openai", "ollama", "vllm", "groq", "fake"],
        default_model="gpt-4o-mini",
        supported_models=supported_models,
        default_budget_ceiling_usd=DEFAULT_BUDGET_CEILING_USD,
        max_budget_ceiling_usd=MAX_ALLOWED_BUDGET_CEILING_USD,
        pricing_rates=rates,
        features=[
            "preflight_budget_enforcement",
            "fail_closed_cost_guardrails",
            "simulated_safe_tool_execution",
            "unprotected_baseline_comparison",
            "offline_deterministic_fake_mode",
        ],
    )


@router.get(
    "/history",
    response_model=list[BenchmarkRunResponse],
    summary="Benchmark Run History",
    description="Returns persisted benchmark runs ordered by timestamp descending.",
    dependencies=[Depends(check_rate_limit)],
)
def get_benchmark_history(
    limit: int = 20,
    offset: int = 0,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_db_session),
) -> list[BenchmarkRunResponse]:
    """Retrieve persisted historical benchmark evaluation records."""
    from sqlalchemy import select

    stmt = (
        select(BenchmarkRunModel)
        .order_by(BenchmarkRunModel.timestamp.desc())
        .offset(offset)
        .limit(min(limit, 100))
    )
    rows = session.execute(stmt).scalars().all()
    return [
        BenchmarkRunResponse(
            run_id=r.run_id,
            timestamp=r.timestamp,
            total_cases=r.total_cases,
            passed_cases=r.passed_cases,
            failed_cases=r.failed_cases,
            accuracy=round((r.passed_cases / r.total_cases) if r.total_cases > 0 else 0.0, 4),
            scenario_pass_rate=1.0,
            metrics=r.metrics,
        )
        for r in rows
    ]


@router.post(
    "/run",
    response_model=BenchmarkRunResponse,
    summary="Trigger Benchmark Execution",
    description=(
        "Executes PromptProbe adversarial evaluation suite and persists metrics. "
        "Restricted to admin role."
    ),
    dependencies=[Depends(check_rate_limit)],
)
def run_benchmark(
    principal: AuthenticatedPrincipal = Depends(require_role("admin")),
    session: Session = Depends(get_db_session),
) -> BenchmarkRunResponse:
    """Execute PromptProbe benchmark programmatically and persist audit run record."""
    if not _BENCHMARK_RUN_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A benchmark execution is currently in progress. "
                "Concurrent benchmark runs are prohibited."
            ),
        )

    try:
        from promptprobe.dataset import load_dataset
        from promptprobe.runner import BenchmarkRunner

        dataset = load_dataset()
        runner = BenchmarkRunner(dataset=dataset)
        report = runner.run()

        now = datetime.now(UTC)
        run_id = uuid4().hex

        passed_count = (
            report.detector_metrics.true_positives + report.detector_metrics.true_negatives
        )
        total_eval = report.detector_metrics.total_samples
        accuracy = (passed_count / total_eval) if total_eval > 0 else 0.0

        metrics_payload = {
            "detector": {
                "total": report.detector_metrics.total_samples,
                "tp": report.detector_metrics.true_positives,
                "fp": report.detector_metrics.false_positives,
                "tn": report.detector_metrics.true_negatives,
                "fn": report.detector_metrics.false_negatives,
                "accuracy": report.detector_metrics.accuracy,
                "precision": report.detector_metrics.precision,
                "recall": report.detector_metrics.recall,
                "f1": report.detector_metrics.f1_score,
            },
            "enforcement": {
                "total": report.enforcement_metrics.total_action_cases,
                "unauthorized_executions": report.enforcement_metrics.unauthorized_executions,
                "correctly_permitted": report.enforcement_metrics.correctly_permitted,
                "correctly_denied": report.enforcement_metrics.correctly_denied,
                "held_for_approval": report.enforcement_metrics.correctly_held_for_approval,
                "accuracy": report.enforcement_metrics.enforcement_accuracy,
            },
        }

        # Persist benchmark record to DB
        passed_cases = (
            passed_count
            + report.enforcement_metrics.correctly_denied
            + report.enforcement_metrics.correctly_permitted
            + report.enforcement_metrics.correctly_held_for_approval
        )
        failed_cases = (
            report.detector_metrics.false_negatives
            + report.detector_metrics.false_positives
            + report.enforcement_metrics.unauthorized_executions
        )

        run_model = BenchmarkRunModel(
            run_id=run_id,
            benchmark_name=dataset.dataset_name,
            timestamp=now,
            total_cases=len(dataset.cases),
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            metrics=metrics_payload,
            environment_info={"executed_by": principal.principal_id},
        )
        session.add(run_model)
        session.commit()

        return BenchmarkRunResponse(
            run_id=run_id,
            timestamp=now,
            total_cases=len(dataset.cases),
            passed_cases=run_model.passed_cases,
            failed_cases=run_model.failed_cases,
            accuracy=round(accuracy, 4),
            scenario_pass_rate=1.0,
            metrics=metrics_payload,
        )
    finally:
        _BENCHMARK_RUN_LOCK.release()
