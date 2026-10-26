"""Benchmark runner executing PromptProbe test cases deterministically against SentinelLLM."""

import random
from datetime import UTC, datetime
from typing import Any

import sentinelllm
from promptprobe.baselines import (
    BASELINE_HEURISTIC,
    BASELINE_NO_DETECTION,
    create_heuristic_defense,
    create_no_detection_baseline,
)
from promptprobe.dataset import load_dataset
from promptprobe.metrics import compute_confusion_matrix, compute_enforcement_metrics
from promptprobe.models import (
    BenchmarkReport,
    CaseEvaluationResult,
    DatasetContainer,
    EvaluationCase,
)
from sentinelllm.contracts.context import RequestContext
from sentinelllm.contracts.messages import (
    RetrievedChunk,
    SecurityContent,
    ToolOutput,
    UserMessage,
)
from sentinelllm.contracts.provenance import ContentProvenance


class BenchmarkRunner:
    """Deterministic evaluation runner for LLM security defenses."""

    def __init__(
        self,
        dataset: DatasetContainer | None = None,
        configuration_name: str = BASELINE_HEURISTIC,
        seed: int = 42,
    ) -> None:
        self.dataset = dataset if dataset is not None else load_dataset()
        self.configuration_name = configuration_name
        self.seed = seed
        random.seed(seed)

        # Initialize requested defense baseline
        if configuration_name == BASELINE_NO_DETECTION:
            self.registry, self.pdp, self.pep = create_no_detection_baseline()
        elif configuration_name == BASELINE_HEURISTIC:
            self.registry, self.pdp, self.pep = create_heuristic_defense()
        else:
            raise ValueError(f"Unknown benchmark configuration: '{configuration_name}'")

    def run(self) -> BenchmarkReport:
        """Execute all test cases in the dataset and generate a comprehensive BenchmarkReport."""
        evaluations: list[tuple[EvaluationCase, CaseEvaluationResult]] = []
        failures: list[dict[str, Any]] = []

        for case in self.dataset.cases:
            try:
                res = self._evaluate_case(case)
            except Exception as ex:  # Confine individual test failures without halting evaluation
                res = CaseEvaluationResult(
                    case_id=case.case_id,
                    category=case.category,
                    success=False,
                    actual_finding=False,
                    error_message=f"Evaluation execution error: {type(ex).__name__}: {ex}",
                )

            evaluations.append((case, res))

            if not res.success:
                failures.append(
                    {
                        "case_id": case.case_id,
                        "category": case.category.value,
                        "description": case.description,
                        "expected_finding": case.expected_finding,
                        "actual_finding": res.actual_finding,
                        "expected_status": case.expected_status,
                        "actual_status": res.actual_status,
                        "expected_reason_code": case.expected_reason_code,
                        "actual_reason_code": res.actual_reason_code,
                        "explanation": case.explanation,
                        "error": res.error_message,
                    }
                )

        detector_metrics = compute_confusion_matrix(evaluations)
        enforcement_metrics = compute_enforcement_metrics(evaluations)

        passed = sum(1 for _, r in evaluations if r.success)
        total = len(evaluations)

        return BenchmarkReport(
            benchmark_name="PromptProbe Adversarial Benchmark",
            dataset_name=self.dataset.dataset_name,
            dataset_version=self.dataset.version,
            package_version=sentinelllm.__version__,
            policy_version=self.pdp.policy_version,
            configuration_name=self.configuration_name,
            run_timestamp=datetime.now(UTC),
            seed=self.seed,
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            detector_metrics=detector_metrics,
            enforcement_metrics=enforcement_metrics,
            failures=failures,
            case_results=[r for _, r in evaluations],
        )

    def _evaluate_case(self, case: EvaluationCase) -> CaseEvaluationResult:
        """Evaluate a test case through content detection or tool enforcement path."""
        # Action authorization evaluation path
        if case.tool_name is not None:
            principal = case.get_principal()
            raw_args = case.tool_arguments if case.tool_arguments is not None else {}

            result = self.pep.invoke(
                tool_name=case.tool_name,
                raw_arguments=raw_args,
                principal=principal,
                context_trust=case.trust_classification,
                request_id=case.case_id,
            )

            actual_status = result.status
            actual_reason = result.reason_code
            actual_decision = result.decision.decision.value if result.decision else None

            # Verify against expected outcomes
            status_match = actual_status == case.expected_status
            reason_match = (
                case.expected_reason_code is None or actual_reason == case.expected_reason_code
            )
            success = status_match and reason_match

            return CaseEvaluationResult(
                case_id=case.case_id,
                category=case.category,
                success=success,
                actual_finding=False,
                actual_decision=actual_decision,
                actual_status=actual_status,
                actual_reason_code=actual_reason,
            )

        # Content detection evaluation path
        item: SecurityContent
        if case.provenance == ContentProvenance.RETRIEVED_DOCUMENT:
            item = RetrievedChunk(
                chunk_id=f"chunk_{case.case_id}",
                content=case.content,
            )
        elif case.provenance == ContentProvenance.EXTERNAL_TOOL:
            item = ToolOutput(
                content=case.content,
                tool_name="simulated_tool",
            )
        else:
            item = UserMessage(
                content=case.content,
            )

        ctx = RequestContext(request_id=case.case_id, items=(item,))
        findings = self.registry.scan_context(ctx)

        actual_finding = len(findings) > 0
        actual_cat = findings[0].category if actual_finding else None

        finding_match = actual_finding == case.expected_finding
        category_match = True
        if case.expected_finding and case.expected_finding_category is not None:
            category_match = any(f.category == case.expected_finding_category for f in findings)

        success = finding_match and category_match

        return CaseEvaluationResult(
            case_id=case.case_id,
            category=case.category,
            success=success,
            actual_finding=actual_finding,
            actual_finding_category=actual_cat,
        )
