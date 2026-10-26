"""Command-line interface for executing PromptProbe benchmark suites."""

import argparse
import sys
from pathlib import Path

from promptprobe.baselines import BASELINE_HEURISTIC, BASELINE_NO_DETECTION
from promptprobe.dataset import load_dataset
from promptprobe.models import BenchmarkReport
from promptprobe.runner import BenchmarkRunner


def format_report_summary(report: BenchmarkReport) -> str:
    """Format benchmark report into a clear human-readable technical summary."""
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


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for PromptProbe benchmark execution."""
    parser = argparse.ArgumentParser(
        prog="promptprobe",
        description="PromptProbe: Reproducible adversarial evaluation for SentinelLLM defenses.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

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
        help="Path to custom benchmark dataset JSON file (defaults to starter dataset)",
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

    args = parser.parse_args(argv)

    # Default to 'run' subcommand if invoked without arguments
    if args.command is None:
        args.command = "run"
        args.config = BASELINE_HEURISTIC
        args.dataset = None
        args.output = None
        args.seed = 42

    try:
        dataset = load_dataset(args.dataset)
        runner = BenchmarkRunner(
            dataset=dataset,
            configuration_name=args.config,
            seed=args.seed,
        )
        report = runner.run()

        # Display human-readable terminal summary
        print(format_report_summary(report))

        # Write machine-readable JSON artifact if requested
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
            print(f"\n[Artifact] Wrote JSON benchmark report to: {out_path.resolve()}")

        return 0 if report.enforcement_metrics.unauthorized_executions == 0 else 1

    except Exception as ex:
        print(f"Error executing PromptProbe benchmark: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
