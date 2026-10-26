"""Deterministic evaluation runner for multi-step adversarial scenario traces."""

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
from promptprobe.dataset import load_scenario_dataset
from promptprobe.scenario_models import (
    ScenarioBenchmarkReport,
    ScenarioDatasetContainer,
    ScenarioMetrics,
    ScenarioResult,
    ScenarioStep,
    ScenarioStepResult,
    ScenarioStepType,
    SecurityScenario,
)
from sentinelllm.approvals.service import ApprovalService
from sentinelllm.approvals.store import InMemoryApprovalStore
from sentinelllm.contracts.decision import SecurityFinding
from sentinelllm.contracts.messages import (
    RetrievedChunk,
    SecurityContent,
    ToolOutput,
    UserMessage,
)
from sentinelllm.contracts.provenance import ContentProvenance, TrustClassification
from sentinelllm.tools.pep import PolicyEnforcementPoint


class ScenarioRunner:
    """Runner executing multi-step security scenarios against SentinelLLM defenses."""

    def __init__(
        self,
        dataset: ScenarioDatasetContainer | None = None,
        configuration_name: str = BASELINE_HEURISTIC,
        seed: int = 42,
    ) -> None:
        self.dataset = dataset if dataset is not None else load_scenario_dataset()
        self.configuration_name = configuration_name
        self.seed = seed
        random.seed(seed)

        if configuration_name not in (BASELINE_HEURISTIC, BASELINE_NO_DETECTION):
            raise ValueError(f"Unknown benchmark configuration: '{configuration_name}'")

    def run(self) -> ScenarioBenchmarkReport:
        """Execute all scenarios in the dataset and compile scenario-level metrics."""
        scenario_results: list[ScenarioResult] = []
        failures: list[dict[str, Any]] = []

        for scenario in self.dataset.scenarios:
            try:
                res = self._evaluate_scenario(scenario)
            except Exception as ex:
                res = ScenarioResult(
                    scenario_id=scenario.scenario_id,
                    category=scenario.category,
                    title=scenario.title,
                    passed=False,
                    total_steps=len(scenario.steps),
                    failure_reasons=[f"Scenario runtime error: {type(ex).__name__}: {ex}"],
                )

            scenario_results.append(res)
            if not res.passed:
                failures.append(
                    {
                        "scenario_id": res.scenario_id,
                        "category": res.category,
                        "title": res.title,
                        "failure_reasons": res.failure_reasons,
                        "step_failures": [
                            sr.model_dump() for sr in res.step_results if not sr.success
                        ],
                    }
                )

        metrics = self._compute_metrics(scenario_results)
        passed_count = sum(1 for r in scenario_results if r.passed)
        total_count = len(scenario_results)

        # Baseline PDP version for reporting
        _, pdp, _ = create_heuristic_defense()

        return ScenarioBenchmarkReport(
            benchmark_name="PromptProbe Multi-Step Scenario Evaluation",
            dataset_name=self.dataset.dataset_name,
            dataset_version=self.dataset.version,
            package_version=sentinelllm.__version__,
            policy_version=pdp.policy_version,
            configuration_name=self.configuration_name,
            run_timestamp=datetime.now(UTC),
            seed=self.seed,
            total_scenarios=total_count,
            passed_scenarios=passed_count,
            failed_scenarios=total_count - passed_count,
            metrics=metrics,
            failures=failures,
            scenario_results=scenario_results,
        )

    def _evaluate_scenario(self, scenario: SecurityScenario) -> ScenarioResult:
        """Deterministically execute an individual multi-step scenario trace."""
        # Initialize isolated defense components for this scenario
        if self.configuration_name == BASELINE_NO_DETECTION:
            registry, pdp, _ = create_no_detection_baseline()
        else:
            registry, pdp, _ = create_heuristic_defense()

        # Shared approval store for scenario lifecycle
        approval_store = InMemoryApprovalStore()
        approval_service = ApprovalService(store=approval_store)
        pep = PolicyEnforcementPoint(
            pdp=pdp,
            approval_service=approval_service,
        )

        trace_items: list[SecurityContent] = []
        accumulated_findings: list[SecurityFinding] = []
        pending_approval_id: str | None = None
        step_results: list[ScenarioStepResult] = []
        failure_reasons: list[str] = []

        for step in scenario.steps:
            try:
                sr, pending_approval_id = self._evaluate_step(
                    step=step,
                    scenario=scenario,
                    registry=registry,
                    pep=pep,
                    approval_service=approval_service,
                    trace_items=trace_items,
                    accumulated_findings=accumulated_findings,
                    pending_approval_id=pending_approval_id,
                )
            except Exception as ex:
                sr = ScenarioStepResult(
                    step_id=step.step_id,
                    step_type=step.step_type,
                    success=False,
                    error_message=f"Step execution exception: {type(ex).__name__}: {ex}",
                )

            step_results.append(sr)
            if not sr.success:
                err_detail = sr.error_message or (
                    f"Step '{step.step_id}' ({step.step_type.value}) invariant failed: "
                    f"expected_status={step.expected_status}, actual={sr.actual_status}, "
                    f"expected_reason={step.expected_reason_code}, "
                    f"actual_reason={sr.actual_reason_code}"
                )
                failure_reasons.append(err_detail)

        scenario_passed = len(failure_reasons) == 0

        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            category=scenario.category,
            title=scenario.title,
            passed=scenario_passed,
            total_steps=len(scenario.steps),
            step_results=step_results,
            failure_reasons=failure_reasons,
        )

    def _evaluate_step(
        self,
        step: ScenarioStep,
        scenario: SecurityScenario,
        registry: Any,
        pep: PolicyEnforcementPoint,
        approval_service: ApprovalService,
        trace_items: list[SecurityContent],
        accumulated_findings: list[SecurityFinding],
        pending_approval_id: str | None,
    ) -> tuple[ScenarioStepResult, str | None]:
        """Execute and verify a single step within a scenario trace."""
        req_id = f"{scenario.scenario_id}_{step.step_id}"

        # 1. User message step
        if step.step_type == ScenarioStepType.USER_MESSAGE:
            msg = UserMessage(content=step.content or "")
            provenance_violation = (
                msg.provenance != ContentProvenance.USER_MESSAGE
                or msg.trust_classification != TrustClassification.USER_INPUT
            )
            trace_items.append(msg)

            step_findings = list(registry.scan_item(msg))
            accumulated_findings.extend(step_findings)

            actual_finding = len(step_findings) > 0
            actual_cat = step_findings[0].category if actual_finding else None

            success = True
            if step.expected_finding is not None and actual_finding != step.expected_finding:
                success = False
            if (
                step.expected_finding_category
                and step.expected_finding
                and not any(f.category == step.expected_finding_category for f in step_findings)
            ):
                success = False
            if provenance_violation:
                success = False

            return (
                ScenarioStepResult(
                    step_id=step.step_id,
                    step_type=step.step_type,
                    success=success,
                    actual_finding=actual_finding,
                    actual_finding_category=actual_cat,
                    provenance_violation=provenance_violation,
                ),
                pending_approval_id,
            )

        # 2. Retrieved document chunk step
        if step.step_type == ScenarioStepType.RETRIEVED_CHUNK:
            chunk = RetrievedChunk(
                chunk_id=step.chunk_id or f"chunk_{step.step_id}",
                content=step.content or "",
            )
            provenance_violation = (
                chunk.provenance != ContentProvenance.RETRIEVED_DOCUMENT
                or chunk.trust_classification != TrustClassification.UNTRUSTED_CONTEXT
            )
            trace_items.append(chunk)

            step_findings = list(registry.scan_item(chunk))
            accumulated_findings.extend(step_findings)

            actual_finding = len(step_findings) > 0
            actual_cat = step_findings[0].category if actual_finding else None

            success = True
            if step.expected_finding is not None and actual_finding != step.expected_finding:
                success = False
            if (
                step.expected_finding_category
                and step.expected_finding
                and not any(f.category == step.expected_finding_category for f in step_findings)
            ):
                success = False
            if provenance_violation:
                success = False

            return (
                ScenarioStepResult(
                    step_id=step.step_id,
                    step_type=step.step_type,
                    success=success,
                    actual_finding=actual_finding,
                    actual_finding_category=actual_cat,
                    provenance_violation=provenance_violation,
                ),
                pending_approval_id,
            )

        # 3. Simulated tool output step
        if step.step_type == ScenarioStepType.TOOL_OUTPUT:
            tout = ToolOutput(
                tool_name=step.tool_name or "external_tool",
                content=step.content or "",
            )
            provenance_violation = (
                tout.provenance != ContentProvenance.EXTERNAL_TOOL
                or tout.trust_classification != TrustClassification.UNTRUSTED_CONTEXT
            )
            trace_items.append(tout)

            step_findings = list(registry.scan_item(tout))
            accumulated_findings.extend(step_findings)

            actual_finding = len(step_findings) > 0
            actual_cat = step_findings[0].category if actual_finding else None

            success = True
            if step.expected_finding is not None and actual_finding != step.expected_finding:
                success = False
            if (
                step.expected_finding_category
                and step.expected_finding
                and not any(f.category == step.expected_finding_category for f in step_findings)
            ):
                success = False
            if provenance_violation:
                success = False

            return (
                ScenarioStepResult(
                    step_id=step.step_id,
                    step_type=step.step_type,
                    success=success,
                    actual_finding=actual_finding,
                    actual_finding_category=actual_cat,
                    provenance_violation=provenance_violation,
                ),
                pending_approval_id,
            )

        # 4. Proposed tool action step
        if step.step_type == ScenarioStepType.TOOL_ACTION:
            principal = step.get_principal()
            raw_args = (
                step.tampered_arguments
                if (step.use_prior_approval and step.tampered_arguments is not None)
                else (step.tool_arguments or {})
            )
            app_id = pending_approval_id if step.use_prior_approval else None

            res = pep.invoke(
                tool_name=step.tool_name or "",
                raw_arguments=raw_args,
                principal=principal,
                findings=tuple(accumulated_findings),
                request_id=req_id,
                approval_id=app_id,
            )

            actual_status = res.status
            actual_reason = res.reason_code
            unauthorized = actual_status == "executed" and step.expected_status != "executed"

            next_pending_approval = (
                res.approval_id if actual_status == "pending_approval" else pending_approval_id
            )

            status_ok = step.expected_status is None or actual_status == step.expected_status
            reason_ok = (
                step.expected_reason_code is None or actual_reason == step.expected_reason_code
            )
            success = status_ok and reason_ok and not unauthorized

            return (
                ScenarioStepResult(
                    step_id=step.step_id,
                    step_type=step.step_type,
                    success=success,
                    actual_status=actual_status,
                    actual_reason_code=actual_reason,
                    unauthorized_execution=unauthorized,
                ),
                next_pending_approval,
            )

        # 5. Approval decision step
        if step.step_type == ScenarioStepType.APPROVAL_DECISION:
            approver = step.get_approver()
            if pending_approval_id is None:
                return (
                    ScenarioStepResult(
                        step_id=step.step_id,
                        step_type=step.step_type,
                        success=False,
                        error_message="Cannot evaluate approval decision: no pending approval ID.",
                    ),
                    None,
                )

            decision = (step.approval_decision or "approve").lower()
            try:
                if decision == "approve":
                    record, _ = approval_service.approve(pending_approval_id, approver=approver)
                else:
                    record, _ = approval_service.reject(
                        pending_approval_id, approver=approver, reason="Scenario rejection"
                    )
                actual_status = record.status.value.lower()
                success = (
                    step.expected_status is None or actual_status == step.expected_status.lower()
                )
                return (
                    ScenarioStepResult(
                        step_id=step.step_id,
                        step_type=step.step_type,
                        success=success,
                        actual_status=actual_status,
                    ),
                    pending_approval_id,
                )
            except Exception as ex:
                return (
                    ScenarioStepResult(
                        step_id=step.step_id,
                        step_type=step.step_type,
                        success=(step.expected_status == "error"),
                        actual_status="error",
                        error_message=str(ex),
                    ),
                    pending_approval_id,
                )

        raise ValueError(f"Unknown scenario step type: '{step.step_type}'")

    def _compute_metrics(self, scenario_results: list[ScenarioResult]) -> ScenarioMetrics:
        """Compute aggregate metrics across evaluated multi-step scenarios."""
        total_scenarios = len(scenario_results)
        passed_scenarios = sum(1 for r in scenario_results if r.passed)
        failed_scenarios = total_scenarios - passed_scenarios

        total_steps = sum(len(r.step_results) for r in scenario_results)
        unauth_exec = sum(
            1 for r in scenario_results for sr in r.step_results if sr.unauthorized_execution
        )
        prov_violations = sum(
            1 for r in scenario_results for sr in r.step_results if sr.provenance_violation
        )

        correctly_blocked = sum(
            1
            for r in scenario_results
            for sr in r.step_results
            if sr.step_type == ScenarioStepType.TOOL_ACTION
            and sr.actual_status == "denied"
            and sr.success
        )
        held_for_approval = sum(
            1
            for r in scenario_results
            for sr in r.step_results
            if sr.step_type == ScenarioStepType.TOOL_ACTION
            and sr.actual_status == "pending_approval"
            and sr.success
        )
        unexpected_exec = sum(
            1 for r in scenario_results for sr in r.step_results if sr.unauthorized_execution
        )
        unexpected_denial = sum(
            1
            for r in scenario_results
            for sr in r.step_results
            if sr.step_type == ScenarioStepType.TOOL_ACTION
            and sr.actual_status == "denied"
            and not sr.success
        )

        success_rate = (passed_scenarios / total_scenarios) if total_scenarios > 0 else 0.0

        return ScenarioMetrics(
            total_scenarios=total_scenarios,
            passed_scenarios=passed_scenarios,
            failed_scenarios=failed_scenarios,
            total_steps_evaluated=total_steps,
            unauthorized_executions=unauth_exec,
            correctly_blocked_actions=correctly_blocked,
            actions_safely_held_for_approval=held_for_approval,
            provenance_violations=prov_violations,
            unexpected_executions=unexpected_exec,
            unexpected_denials=unexpected_denial,
            scenario_success_rate=success_rate,
            notes="Multi-step scenarios require all step invariants to hold for scenario pass.",
        )
