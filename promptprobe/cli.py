"""Command-line interface for executing PromptProbe benchmark suites."""

import argparse
import sys
from pathlib import Path

from promptprobe.baselines import BASELINE_HEURISTIC, BASELINE_NO_DETECTION
from promptprobe.dataset import load_dataset, load_scenario_dataset
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

    args = parser.parse_args(argv)

    if args.command is None:
        args.command = "run"
        args.config = BASELINE_HEURISTIC
        args.dataset = None
        args.output = None
        args.seed = 42
        args.include_scenarios = False

    try:
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
