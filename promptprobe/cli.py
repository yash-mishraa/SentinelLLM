"""Command-line interface for executing PromptProbe benchmark suites."""

import argparse
import sys
from pathlib import Path

from promptprobe.baselines import BASELINE_HEURISTIC, BASELINE_NO_DETECTION
from promptprobe.dataset import load_dataset, load_scenario_dataset
from promptprobe.hybrid import HybridBenchmarkRunner
from promptprobe.hybrid_models import HybridBenchmarkReport
from promptprobe.models import BenchmarkReport
from promptprobe.runner import BenchmarkRunner
from promptprobe.scenario_models import ScenarioBenchmarkReport
from promptprobe.scenario_runner import ScenarioRunner


def format_report_summary(report: BenchmarkReport) -> str:
    """Format single-case benchmark report into a clear human-readable technical summary."""
    det = report.detector_metrics
    enf = report.enforcement_metrics

    p_str = f"{det.precision:.4f}" if det.precision is not None else "N/A"
    r_str = f"{det.recall:.4f}" if det.recall is not None else "N/A"
    f1_str = f"{det.f1_score:.4f}" if det.f1_score is not None else "N/A"
    fpr_str = f"{det.false_positive_rate:.4f}" if det.false_positive_rate is not None else "N/A"
    enf_acc = f"{enf.enforcement_accuracy:.4f}" if enf.enforcement_accuracy is not None else "N/A"

    lines: list[str] = [
        "=" * 78,
        f" PromptProbe Adversarial Evaluation Report ({report.configuration_name})",
        "=" * 78,
        f"Dataset:       {report.dataset_name} ({report.total_cases} cases)",
        f"Version:       Dataset v{report.dataset_version} | Package {report.package_version}",
        f"Policy Ver:    {report.policy_version}",
        f"Timestamp:     {report.run_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Random Seed:   {report.seed}",
        "-" * 78,
        "1. PROBABILISTIC DETECTOR METRICS (Content Classification)",
        "-" * 78,
        f"  Total Detector Samples:   {det.total_samples}",
        f"  True Positives (TP):      {det.true_positives}",
        f"  False Positives (FP):     {det.false_positives}",
        f"  True Negatives (TN):      {det.true_negatives}",
        f"  False Negatives (FN):     {det.false_negatives}",
        f"  Precision:                {p_str}",
        f"  Recall (Detection Rate):  {r_str}",
        f"  F1 Score:                 {f1_str}",
        f"  Accuracy:                 {det.accuracy:.4f}",
        f"  False Positive Rate (FPR):{fpr_str}",
    ]
    if det.notes:
        lines.append(f"  Notes:                    {det.notes}")

    lines.extend(
        [
            "-" * 78,
            "2. DETERMINISTIC ACTION ENFORCEMENT METRICS (Tool Authorization)",
            "-" * 78,
            f"  Total Action Cases:       {enf.total_action_cases}",
            f"  Unauthorized Executions:  {enf.unauthorized_executions} (Target: 0)",
            f"  Correctly Permitted:      {enf.correctly_permitted}",
            f"  Correctly Denied:         {enf.correctly_denied}",
            f"  Safely Held for Approval: {enf.correctly_held_for_approval}",
            f"  Invalid/Unknown Blocked:  {enf.invalid_or_unknown_prevented}",
            f"  Enforcement Accuracy:     {enf_acc}",
            "-" * 78,
            f"OVERALL EVALUATION: {report.passed_cases}/{report.total_cases} passed specification",
            "=" * 78,
        ]
    )

    if report.failures:
        lines.append("\nFAILURES IDENTIFIED:")
        for idx, fail in enumerate(report.failures, 1):
            lines.append(f"  [{idx}] Case ID: {fail['case_id']} ({fail['category']})")
            lines.append(
                f"      Finding: expected={fail['expected_finding']}, got={fail['actual_finding']}"
            )
            if fail.get("expected_status"):
                lines.append(
                    f"      Status:  expected={fail['expected_status']} got={fail['actual_status']}"
                )
            lines.append(f"      Rationale: {fail['explanation']}")
            if fail.get("error"):
                lines.append(f"      Error: {fail['error']}")

    return "\n".join(lines)


def format_scenario_report_summary(report: ScenarioBenchmarkReport) -> str:
    """Format multi-step scenario evaluation report into technical summary."""
    m = report.metrics
    lines: list[str] = [
        "=" * 78,
        f" PromptProbe Multi-Step Scenario Evaluation ({report.configuration_name})",
        "=" * 78,
        f"Dataset:       {report.dataset_name} ({report.total_scenarios} scenarios)",
        f"Version:       Dataset v{report.dataset_version} | Package {report.package_version}",
        f"Policy Ver:    {report.policy_version}",
        f"Timestamp:     {report.run_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Random Seed:   {report.seed}",
        "-" * 78,
        "SCENARIO & ENFORCEMENT METRICS",
        "-" * 78,
        f"  Total Scenarios Evaluated: {m.total_scenarios}",
        f"  Total Steps Evaluated:     {m.total_steps_evaluated}",
        f"  Passed Scenarios:          {m.passed_scenarios}",
        f"  Failed Scenarios:          {m.failed_scenarios}",
        f"  Scenario Pass Rate:        {m.scenario_success_rate:.2%}",
        f"  Unauthorized Executions:   {m.unauthorized_executions} (Target: 0)",
        f"  Correctly Blocked Actions: {m.correctly_blocked_actions}",
        f"  Safely Held for Approval:  {m.actions_safely_held_for_approval}",
        f"  Provenance Violations:     {m.provenance_violations} (Target: 0)",
        f"  Unexpected Executions:     {m.unexpected_executions}",
        f"  Unexpected Denials:        {m.unexpected_denials}",
        "-" * 78,
        (
            f"OVERALL EVALUATION: {report.passed_scenarios}/{report.total_scenarios} "
            f"scenarios passed all security invariants"
        ),
        "=" * 78,
    ]

    if report.failures:
        lines.append("\nSCENARIO FAILURES IDENTIFIED:")
        for idx, fail in enumerate(report.failures, 1):
            lines.append(f"  [{idx}] Scenario ID: {fail['scenario_id']} ({fail['category']})")
            lines.append(f"      Title: {fail['title']}")
            for reason in fail.get("failure_reasons", []):
                lines.append(f"      Failure Reason: {reason}")

    return "\n".join(lines)


def run_benchmark(
    config: str,
    dataset_path: str | None,
    output_path: str | None,
    seed: int,
) -> int:
    """Execute single-case benchmark evaluation."""
    dataset = load_dataset(dataset_path)
    runner = BenchmarkRunner(
        dataset=dataset,
        configuration_name=config,
        seed=seed,
    )
    report = runner.run()
    print(format_report_summary(report))

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        print(f"\n[Artifact] Wrote JSON benchmark report to: {out.resolve()}")

    return 0 if report.enforcement_metrics.unauthorized_executions == 0 else 1


def run_scenarios(
    config: str,
    scenario_path: str | None,
    output_path: str | None,
    seed: int,
) -> int:
    """Execute multi-step scenario evaluation."""
    dataset = load_scenario_dataset(scenario_path)
    runner = ScenarioRunner(
        dataset=dataset,
        configuration_name=config,
        seed=seed,
    )
    report = runner.run()
    print(format_scenario_report_summary(report))

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        print(f"\n[Artifact] Wrote JSON scenario report to: {out.resolve()}")

    return 0 if report.metrics.unauthorized_executions == 0 else 1


def format_hybrid_report_summary(report: HybridBenchmarkReport) -> str:
    """Format hybrid evaluation report into a clear technical summary."""
    m = report.metrics
    p_str = f"{m.gateway_precision:.4f}" if m.gateway_precision is not None else "N/A"
    r_str = f"{m.gateway_recall:.4f}" if m.gateway_recall is not None else "N/A"
    f1_str = f"{m.gateway_f1:.4f}" if m.gateway_f1 is not None else "N/A"

    mode_label = "LIVE NETWORK EVALUATION" if report.is_live else "OFFLINE SYNTHETIC SIMULATION"

    lines: list[str] = [
        "=" * 78,
        f" PromptProbe Hybrid Evaluation Report ({report.provider} / {report.model})",
        "=" * 78,
        f"Dataset:       {report.dataset_name} ({m.total_cases} cases evaluated)",
        f"Version:       Dataset v{report.dataset_version}",
        f"Mode:          {mode_label}",
        f"Timestamp:     {report.run_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "-" * 78,
        "1. SENTINELLLM GATEWAY METRICS (Content Classification Layer)",
        "-" * 78,
        f"  Evaluated Content Cases:  {m.content_cases}",
        f"  Attacks Intercepted (TP): {m.attacks_blocked_by_gateway}",
        f"  Attacks Leaked to LLM(FN):{m.attacks_reaching_model}",
        f"  Benign Passed to LLM(TN): {m.benign_dispatched}",
        f"  Benign False Alarms (FP): {m.benign_blocked_by_gateway}",
        f"  Gateway Precision:        {p_str}",
        f"  Gateway Recall:           {r_str}",
        f"  Gateway F1 Score:         {f1_str}",
        f"  Gateway Accuracy:         {m.gateway_accuracy:.4f}",
        "-" * 78,
        "2. POLICY ENFORCEMENT METRICS (Tool Authorization Layer)",
        "-" * 78,
        f"  Evaluated Action Cases:   {m.action_cases}",
        f"  Actions Enforced:         {m.actions_enforced_correctly}",
        f"  Unauthorized Prevented:   {m.unauthorized_actions_prevented}",
        "-" * 78,
        "3. MODEL TELEMETRY & COST EFFICIENCY",
        "-" * 78,
        f"  Total Tokens Consumed:    {m.total_tokens_consumed}",
        f"  Tokens Saved by Gateway:  {m.tokens_saved_by_gateway}",
        (
            f"  Total Cost (USD):         ${m.total_cost_usd:.6f} "
            f"{'(Estimated)' if m.is_cost_estimated else '(Reported)'}"
        ),
        f"  Provider Failures:        {m.provider_failures}",
        (
            f"  Budget Exhausted:         "
            f"{'YES (Halted early)' if m.budget_exhausted else 'NO (Within budget)'}"
        ),
        "=" * 78,
    ]
    return "\n".join(lines)


def run_hybrid(
    provider: str,
    model: str | None,
    mode: str,
    base_url: str | None,
    max_budget: float,
    max_cases: int | None,
    live_opt_in: bool,
    unprotected: bool,
    dataset_path: str | None,
    output_path: str | None,
) -> int:
    """Execute hybrid evaluation across SentinelLLM gateway and model adapter."""
    from sentinelllm.adapters import (
        MAX_ALLOWED_BUDGET_CEILING_USD,
        BaseLLMAdapter,
        BudgetTracker,
        FakeLLMAdapter,
        LLMConfig,
        OpenAICompatibleAdapter,
        RunBudget,
        SafetyOptInRequiredError,
    )

    if provider != "fake" and not live_opt_in:
        raise SafetyOptInRequiredError(
            "Safety guard: live LLM evaluation requires --live-opt-in confirmation flag."
        )

    dataset = load_dataset(dataset_path)

    budget_usd = min(max_budget, MAX_ALLOWED_BUDGET_CEILING_USD)
    budget = RunBudget(max_cost_usd=budget_usd)
    tracker = BudgetTracker(budget=budget)

    adapter: BaseLLMAdapter
    if provider == "openai":
        target_model = model or "gpt-4o-mini"
        config = LLMConfig(
            provider="openai",
            model=target_model,
            base_url=base_url,
            live_opt_in=live_opt_in,
        )
        adapter = OpenAICompatibleAdapter(config=config, budget_tracker=tracker)
    else:
        target_model = model or "fake-model"
        config = LLMConfig(
            provider="fake",
            model=target_model,
        )
        adapter = FakeLLMAdapter(
            config=config,
            budget_tracker=tracker,
            mode=mode,
        )

    runner = HybridBenchmarkRunner(
        adapter=adapter,
        dataset=dataset,
        budget_tracker=tracker,
        unprotected_baseline=unprotected,
        max_cases=max_cases,
    )

    report = runner.run()
    print(format_hybrid_report_summary(report))

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        print(f"\n[Artifact] Wrote JSON hybrid benchmark report to: {out.resolve()}")

    return 0 if report.metrics.provider_failures == 0 else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for PromptProbe benchmark execution."""
    parser = argparse.ArgumentParser(
        prog="promptprobe",
        description="PromptProbe: Reproducible adversarial evaluation for SentinelLLM defenses.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # 1. run command (single-case evaluations)
    run_parser = subparsers.add_parser("run", help="Run benchmark suite against target defense")
    run_parser.add_argument(
        "--config",
        choices=[BASELINE_HEURISTIC, BASELINE_NO_DETECTION],
        default=BASELINE_HEURISTIC,
        help="Defense baseline configuration to evaluate (default: heuristic_defense)",
    )
    run_parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to custom benchmark dataset JSON file",
    )
    run_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write full JSON benchmark report artifact",
    )
    run_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic pseudorandom seed (default: 42)",
    )
    run_parser.add_argument(
        "--include-scenarios",
        action="store_true",
        help="Also run multi-step scenarios after single cases",
    )

    # 2. scenarios command (multi-step traces)
    scen_parser = subparsers.add_parser(
        "scenarios", help="Run multi-step adversarial scenario evaluations"
    )
    scen_parser.add_argument(
        "--config",
        choices=[BASELINE_HEURISTIC, BASELINE_NO_DETECTION],
        default=BASELINE_HEURISTIC,
        help="Defense baseline configuration to evaluate (default: heuristic_defense)",
    )
    scen_parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to custom scenario dataset JSON file",
    )
    scen_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write full JSON scenario report artifact",
    )
    scen_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic pseudorandom seed (default: 42)",
    )

    # 3. demo command (end-to-end walkthrough)
    subparsers.add_parser("demo", help="Run end-to-end interactive runtime security demonstration")

    # 4. hybrid command (SentinelLLM + LLM Adapter)
    hybrid_parser = subparsers.add_parser(
        "hybrid", help="Run hybrid evaluation across SentinelLLM gateway and LLM adapter"
    )
    hybrid_parser.add_argument(
        "--provider",
        choices=["fake", "openai"],
        default="fake",
        help="LLM provider adapter to evaluate (default: fake for offline testing)",
    )
    hybrid_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model identifier (e.g. 'gpt-4o-mini', 'mock-model')",
    )
    hybrid_parser.add_argument(
        "--mode",
        choices=["standard", "refusal", "vulnerable"],
        default="standard",
        help="Simulated model behavioral mode for fake adapter (default: standard)",
    )
    hybrid_parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Optional base URL for OpenAI-compatible endpoints (e.g. local Ollama)",
    )
    hybrid_parser.add_argument(
        "--max-budget",
        type=float,
        default=0.20,
        help="Maximum run budget ceiling in USD (default: $0.20, ceiling: $1.00)",
    )
    hybrid_parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Maximum number of cases to evaluate (default: all)",
    )
    hybrid_parser.add_argument(
        "--live-opt-in",
        action="store_true",
        help="Explicit confirmation required to make live network calls",
    )
    hybrid_parser.add_argument(
        "--unprotected",
        action="store_true",
        help="Evaluate unprotected baseline without SentinelLLM gateway interception",
    )
    hybrid_parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to custom benchmark dataset JSON file",
    )
    hybrid_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write full JSON hybrid report artifact",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        args.command = "run"
        args.config = BASELINE_HEURISTIC
        args.dataset = None
        args.output = None
        args.seed = 42
        args.include_scenarios = False

    try:
        if args.command == "demo":
            from sentinelllm.demo import run_demo

            return run_demo()

        if args.command == "hybrid":
            return run_hybrid(
                provider=args.provider,
                model=args.model,
                mode=args.mode,
                base_url=args.base_url,
                max_budget=args.max_budget,
                max_cases=args.max_cases,
                live_opt_in=args.live_opt_in,
                unprotected=args.unprotected,
                dataset_path=args.dataset,
                output_path=args.output,
            )

        if args.command == "scenarios":
            return run_scenarios(
                config=args.config,
                scenario_path=args.dataset,
                output_path=args.output,
                seed=args.seed,
            )

        # Single-case run
        res = run_benchmark(
            config=args.config,
            dataset_path=args.dataset,
            output_path=args.output,
            seed=args.seed,
        )
        if getattr(args, "include_scenarios", False):
            print("\n")
            scen_res = run_scenarios(
                config=args.config,
                scenario_path=None,
                output_path=None,
                seed=args.seed,
            )
            return 0 if (res == 0 and scen_res == 0) else 1

        return res

    except Exception as ex:
        print(f"Error executing PromptProbe benchmark: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
