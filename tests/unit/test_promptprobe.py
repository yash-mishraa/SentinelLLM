"""Unit and integration test suite for the PromptProbe adversarial evaluation harness."""

import json
from pathlib import Path

import pytest

from promptprobe.baselines import (
    BASELINE_HEURISTIC,
    BASELINE_NO_DETECTION,
)
from promptprobe.dataset import load_dataset
from promptprobe.metrics import compute_confusion_matrix, compute_enforcement_metrics
from promptprobe.models import (
    CaseEvaluationResult,
    DatasetContainer,
    EvaluationCase,
    EvaluationCategory,
)
from promptprobe.runner import BenchmarkRunner


class TestPromptProbeDataset:
    """Tests covering dataset loading, schema validation, and constraint invariants."""

    def test_default_dataset_loads_and_validates(self) -> None:
        dataset = load_dataset()
        assert dataset.dataset_name == "promptprobe_starter_adversarial"
        assert dataset.version == "1.0.0"
        assert len(dataset.cases) >= 20

    def test_duplicate_case_ids_rejected(self) -> None:
        case = EvaluationCase(
            case_id="DUP-001",
            category=EvaluationCategory.BENIGN_USER,
            description="Duplicate test",
            content="Hello world",
        )
        with pytest.raises(ValueError, match="Duplicate case_id"):
            DatasetContainer(
                dataset_name="test_dup",
                version="1.0.0",
                description="test",
                disclaimer="test",
                cases=[case, case],
            )

    def test_missing_dataset_file_raises_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_dataset("/tmp/non_existent_dataset_file_xyz.json")

    def test_malformed_json_raises_value_error(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("{ unquoted_key: invalid }", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed JSON"):
            load_dataset(bad_json)


class TestPromptProbeMetrics:
    """Tests covering precision, recall, F1, confusion matrix, and enforcement calculations."""

    def test_confusion_matrix_perfect_classification(self) -> None:
        c_pos = EvaluationCase(
            case_id="P1",
            category=EvaluationCategory.DIRECT_INJECTION,
            description="Pos",
            content="test",
            expected_finding=True,
        )
        r_pos = CaseEvaluationResult(
            case_id="P1",
            category=EvaluationCategory.DIRECT_INJECTION,
            success=True,
            actual_finding=True,
        )

        c_neg = EvaluationCase(
            case_id="N1",
            category=EvaluationCategory.BENIGN_USER,
            description="Neg",
            content="test",
            expected_finding=False,
        )
        r_neg = CaseEvaluationResult(
            case_id="N1",
            category=EvaluationCategory.BENIGN_USER,
            success=True,
            actual_finding=False,
        )

        matrix = compute_confusion_matrix([(c_pos, r_pos), (c_neg, r_neg)])
        assert matrix.true_positives == 1
        assert matrix.false_positives == 0
        assert matrix.true_negatives == 1
        assert matrix.false_negatives == 0
        assert matrix.precision == 1.0
        assert matrix.recall == 1.0
        assert matrix.f1_score == 1.0
        assert matrix.accuracy == 1.0
        assert matrix.false_positive_rate == 0.0

    def test_confusion_matrix_zero_positives_handles_division_by_zero(self) -> None:
        """When zero positive samples exist, precision and recall return None without raising."""
        c_neg = EvaluationCase(
            case_id="N1",
            category=EvaluationCategory.BENIGN_USER,
            description="Neg",
            content="test",
            expected_finding=False,
        )
        r_neg = CaseEvaluationResult(
            case_id="N1",
            category=EvaluationCategory.BENIGN_USER,
            success=True,
            actual_finding=False,
        )

        matrix = compute_confusion_matrix([(c_neg, r_neg)])
        assert matrix.true_positives == 0
        assert matrix.false_positives == 0
        assert matrix.true_negatives == 1
        assert matrix.false_negatives == 0
        assert matrix.precision is None
        assert matrix.recall is None
        assert matrix.f1_score is None
        assert matrix.accuracy == 1.0
        assert "zero positive predictions" in matrix.notes

    def test_enforcement_metrics_correctly_categorizes_actions(self) -> None:
        c1 = EvaluationCase(
            case_id="A1",
            category=EvaluationCategory.TOOL_AUTHORIZED,
            description="Permitted",
            content="run",
            tool_name="search_documents",
            expected_status="executed",
        )
        r1 = CaseEvaluationResult(
            case_id="A1",
            category=EvaluationCategory.TOOL_AUTHORIZED,
            success=True,
            actual_finding=False,
            actual_status="executed",
        )

        c2 = EvaluationCase(
            case_id="A2",
            category=EvaluationCategory.TOOL_UNAUTHORIZED,
            description="Denied",
            content="run",
            tool_name="read_customer_record",
            expected_status="denied",
            expected_reason_code="DENY_INSUFFICIENT_PERMISSION",
        )
        r2 = CaseEvaluationResult(
            case_id="A2",
            category=EvaluationCategory.TOOL_UNAUTHORIZED,
            success=True,
            actual_finding=False,
            actual_status="denied",
        )

        c3 = EvaluationCase(
            case_id="A3",
            category=EvaluationCategory.TOOL_REQUIRES_APPROVAL,
            description="Review",
            content="run",
            tool_name="export_customer_records",
            expected_status="pending_approval",
        )
        r3 = CaseEvaluationResult(
            case_id="A3",
            category=EvaluationCategory.TOOL_REQUIRES_APPROVAL,
            success=True,
            actual_finding=False,
            actual_status="pending_approval",
        )

        metrics = compute_enforcement_metrics([(c1, r1), (c2, r2), (c3, r3)])
        assert metrics.total_action_cases == 3
        assert metrics.unauthorized_executions == 0
        assert metrics.correctly_permitted == 1
        assert metrics.correctly_denied == 1
        assert metrics.correctly_held_for_approval == 1
        assert metrics.enforcement_accuracy == 1.0

    def test_enforcement_unauthorized_execution_detected(self) -> None:
        """When an action expected to be denied executes, it is flagged as unauthorized."""
        c = EvaluationCase(
            case_id="BAD1",
            category=EvaluationCategory.TOOL_UNAUTHORIZED,
            description="Should deny",
            content="run",
            tool_name="read_customer_record",
            expected_status="denied",
        )
        # Violation: Tool executed despite expecting denial
        r = CaseEvaluationResult(
            case_id="BAD1",
            category=EvaluationCategory.TOOL_UNAUTHORIZED,
            success=False,
            actual_finding=False,
            actual_status="executed",
        )

        metrics = compute_enforcement_metrics([(c, r)])
        assert metrics.unauthorized_executions == 1
        assert metrics.correctly_denied == 0


class TestPromptProbeRunner:
    """Integration tests running benchmark baselines, report generation, and CLI."""

    def test_deterministic_repeated_runs_yield_identical_metrics(self) -> None:
        dataset = load_dataset()
        runner1 = BenchmarkRunner(dataset=dataset, configuration_name=BASELINE_HEURISTIC, seed=42)
        runner2 = BenchmarkRunner(dataset=dataset, configuration_name=BASELINE_HEURISTIC, seed=42)

        report1 = runner1.run()
        report2 = runner2.run()

        assert report1.total_cases == report2.total_cases
        assert report1.passed_cases == report2.passed_cases
        assert report1.detector_metrics.accuracy == report2.detector_metrics.accuracy
        assert (
            report1.enforcement_metrics.unauthorized_executions
            == report2.enforcement_metrics.unauthorized_executions
        )

    def test_no_detection_baseline_evaluation(self) -> None:
        dataset = load_dataset()
        runner = BenchmarkRunner(dataset=dataset, configuration_name=BASELINE_NO_DETECTION, seed=42)
        report = runner.run()

        assert report.configuration_name == BASELINE_NO_DETECTION
        assert report.detector_metrics.true_positives == 0
        assert report.detector_metrics.recall == 0.0
        # Policy enforcement remains 100% correct even without content detectors
        assert report.enforcement_metrics.unauthorized_executions == 0
        assert report.enforcement_metrics.enforcement_accuracy == 1.0

    def test_json_report_serialization(self, tmp_path: Path) -> None:
        dataset = load_dataset()
        runner = BenchmarkRunner(dataset=dataset, configuration_name=BASELINE_HEURISTIC, seed=42)
        report = runner.run()

        json_path = tmp_path / "benchmark_report.json"
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        # Verify load back
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["benchmark_name"] == "PromptProbe Adversarial Benchmark"
        assert "detector_metrics" in data
        assert "enforcement_metrics" in data
        assert data["enforcement_metrics"]["unauthorized_executions"] == 0

    def test_malformed_case_fails_safely_without_crashing_runner(self) -> None:
        """Internal execution exceptions fail gracefully without interrupting remaining cases."""
        good_case = EvaluationCase(
            case_id="G1",
            category=EvaluationCategory.BENIGN_USER,
            description="Good",
            content="Hello",
        )
        bad_case = EvaluationCase(
            case_id="B1",
            category=EvaluationCategory.TOOL_AUTHORIZED,
            description="Bad tool arguments",
            content="run",
            tool_name="search_documents",
            tool_arguments=None,  # triggers handling in runner
            expected_status="denied",
        )

        custom_dataset = DatasetContainer(
            dataset_name="custom_fail_test",
            version="1.0.0",
            description="Test",
            disclaimer="Test",
            cases=[good_case, bad_case],
        )

        runner = BenchmarkRunner(dataset=custom_dataset, configuration_name=BASELINE_HEURISTIC)
        report = runner.run()
        assert report.total_cases == 2
        assert len(report.case_results) == 2

    def test_cli_execution_succeeds(self, capsys: pytest.CaptureFixture[str]) -> None:
        from promptprobe.cli import main

        exit_code = main(["run", "--config", BASELINE_HEURISTIC])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "PromptProbe Adversarial Evaluation Report" in captured.out
        assert "PROBABILISTIC DETECTOR METRICS" in captured.out
        assert "DETERMINISTIC ACTION ENFORCEMENT METRICS" in captured.out

    def test_cli_execution_with_output_file_and_default_command(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from promptprobe.cli import main

        out_file = tmp_path / "cli_report.json"
        exit_code = main(["run", "--output", str(out_file)])
        assert exit_code == 0
        assert out_file.is_file()
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert "detector_metrics" in data
        assert "enforcement_metrics" in data

        exit_code_default = main([])
        assert exit_code_default == 0

    def test_cli_execution_error_handling(self, capsys: pytest.CaptureFixture[str]) -> None:
        from promptprobe.cli import main

        exit_code = main(["run", "--dataset", "/tmp/non_existent_dataset_987654.json"])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "Error executing PromptProbe benchmark" in captured.err

    def test_main_module_execution(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import runpy

        monkeypatch.setattr("sys.argv", ["promptprobe", "run"])
        with pytest.raises(SystemExit) as exc:
            runpy.run_module("promptprobe", run_name="__main__")
        assert exc.value.code == 0
