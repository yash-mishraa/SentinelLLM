"""Unit and regression tests for PromptProbe multi-step adversarial scenario evaluations."""

import json
from pathlib import Path

import pytest

from promptprobe.dataset import load_scenario_dataset
from promptprobe.scenario_models import (
    ScenarioBenchmarkReport,
    ScenarioDatasetContainer,
    ScenarioStep,
    ScenarioStepType,
    SecurityScenario,
)
from promptprobe.scenario_runner import ScenarioRunner


class TestScenarioDataset:
    """Tests covering dataset loading, validation, and schema invariants."""

    def test_default_scenario_dataset_loads_and_validates(self) -> None:
        dataset = load_scenario_dataset()
        assert dataset.dataset_name == "promptprobe_starter_scenarios"
        assert dataset.version == "1.0.0"
        assert len(dataset.scenarios) == 10

    def test_duplicate_scenario_ids_rejected(self) -> None:
        scen = SecurityScenario(
            scenario_id="DUP-SCEN-001",
            category="test",
            title="Duplicate scenario",
            description="Test duplicate IDs",
            steps=[
                ScenarioStep(
                    step_id="s1",
                    step_type=ScenarioStepType.USER_MESSAGE,
                    content="Hello",
                )
            ],
        )
        with pytest.raises(ValueError, match="Duplicate scenario_id"):
            ScenarioDatasetContainer(
                dataset_name="test_dup",
                version="1.0.0",
                description="desc",
                disclaimer="disclaimer",
                scenarios=[scen, scen],
            )

    def test_missing_scenario_file_raises_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="Scenario dataset file not found"):
            load_scenario_dataset("/tmp/non_existent_scenarios_file_xyz.json")

    def test_malformed_json_raises_value_error(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "bad_scenarios.json"
        bad_json.write_text("{ unquoted_key: invalid }", encoding="utf-8")
        with pytest.raises(ValueError, match="Malformed JSON in scenario dataset"):
            load_scenario_dataset(bad_json)


class TestScenarioRunnerExecution:
    """Tests verifying deterministic multi-step scenario execution and defense invariants."""

    def test_deterministic_execution_of_same_scenario(self) -> None:
        runner1 = ScenarioRunner(seed=123)
        runner2 = ScenarioRunner(seed=123)
        report1 = runner1.run()
        report2 = runner2.run()

        assert report1.total_scenarios == report2.total_scenarios
        assert report1.passed_scenarios == report2.passed_scenarios
        assert report1.metrics.unauthorized_executions == report2.metrics.unauthorized_executions
        assert (
            report1.metrics.correctly_blocked_actions == report2.metrics.correctly_blocked_actions
        )

    def test_zero_unauthorized_executions_invariant(self) -> None:
        runner = ScenarioRunner()
        report = runner.run()

        # Invariant: unauthorized executions must strictly remain 0
        assert report.metrics.unauthorized_executions == 0
        assert report.passed_scenarios == 10
        assert report.failed_scenarios == 0
        assert report.metrics.provenance_violations == 0

    def test_source_and_provenance_preservation_between_steps(self) -> None:
        dataset = load_scenario_dataset()
        benign_scen = next(
            s for s in dataset.scenarios if s.scenario_id == "SCEN-01-BENIGN-MULTI-TURN"
        )

        single_container = ScenarioDatasetContainer(
            dataset_name="single_test",
            version="1.0.0",
            description="desc",
            disclaimer="disclaimer",
            scenarios=[benign_scen],
        )
        runner = ScenarioRunner(dataset=single_container)
        report = runner.run()

        assert report.passed_scenarios == 1
        res = report.scenario_results[0]
        assert res.passed is True
        assert len(res.step_results) == 4
        assert all(not sr.provenance_violation for sr in res.step_results)

    def test_injection_in_retrieved_content_and_tool_output(self) -> None:
        dataset = load_scenario_dataset()
        rag_scen = next(
            s for s in dataset.scenarios if s.scenario_id == "SCEN-03-RAG-INDIRECT-INJECTION"
        )
        tool_scen = next(
            s for s in dataset.scenarios if s.scenario_id == "SCEN-04-TOOL-OUTPUT-INDIRECT-INJ"
        )

        single_container = ScenarioDatasetContainer(
            dataset_name="indirect_inj_test",
            version="1.0.0",
            description="desc",
            disclaimer="disclaimer",
            scenarios=[rag_scen, tool_scen],
        )
        runner = ScenarioRunner(dataset=single_container)
        report = runner.run()

        assert report.passed_scenarios == 2
        for r in report.scenario_results:
            assert r.passed is True
            # Confirm detector flagged injection in non-user step
            content_step = next(sr for sr in r.step_results if sr.step_id == "s2")
            assert content_step.actual_finding is True
            assert content_step.actual_finding_category == "prompt_injection"

    def test_prompt_based_identity_and_instruction_spoofing(self) -> None:
        dataset = load_scenario_dataset()
        spoof_scen = next(
            s for s in dataset.scenarios if s.scenario_id == "SCEN-05-ADMIN-IMPERSONATION-SPOOF"
        )
        single_container = ScenarioDatasetContainer(
            dataset_name="spoof_test",
            version="1.0.0",
            description="desc",
            disclaimer="disclaimer",
            scenarios=[spoof_scen],
        )
        runner = ScenarioRunner(dataset=single_container)
        report = runner.run()

        assert report.passed_scenarios == 1
        res = report.scenario_results[0]
        assert res.passed is True
        action_step = next(sr for sr in res.step_results if sr.step_id == "s2")
        assert action_step.actual_status == "denied"
        assert action_step.actual_reason_code == "DENY_INSUFFICIENT_PERMISSION"
        assert action_step.unauthorized_execution is False

    def test_canary_exposure_halts_execution(self) -> None:
        dataset = load_scenario_dataset()
        canary_scen = next(
            s for s in dataset.scenarios if s.scenario_id == "SCEN-06-CANARY-EXPOSURE"
        )
        single_container = ScenarioDatasetContainer(
            dataset_name="canary_test",
            version="1.0.0",
            description="desc",
            disclaimer="disclaimer",
            scenarios=[canary_scen],
        )
        runner = ScenarioRunner(dataset=single_container)
        report = runner.run()

        assert report.passed_scenarios == 1
        res = report.scenario_results[0]
        assert res.passed is True
        action_step = next(sr for sr in res.step_results if sr.step_id == "s2")
        assert action_step.actual_status == "denied"
        assert action_step.actual_reason_code == "DENY_HIGH_RISK_FINDINGS"

    def test_clean_detector_results_with_denied_authorization(self) -> None:
        dataset = load_scenario_dataset()
        benign_sec = next(
            s
            for s in dataset.scenarios
            if s.scenario_id == "SCEN-07-BENIGN-SEC-RESEARCH-DENIED-TOOL"
        )
        single_container = ScenarioDatasetContainer(
            dataset_name="clean_denied_test",
            version="1.0.0",
            description="desc",
            disclaimer="disclaimer",
            scenarios=[benign_sec],
        )
        runner = ScenarioRunner(dataset=single_container)
        report = runner.run()

        assert report.passed_scenarios == 1
        res = report.scenario_results[0]
        # Verify content steps had 0 findings
        for sr in res.step_results[:2]:
            assert sr.actual_finding is False
        # Verify action step was still denied because principal lacked permission
        action_step = res.step_results[2]
        assert action_step.actual_status == "denied"
        assert action_step.actual_reason_code == "DENY_INSUFFICIENT_PERMISSION"

    def test_approval_lifecycle_and_tampered_request_rejection(self) -> None:
        dataset = load_scenario_dataset()
        app_scen = next(
            s for s in dataset.scenarios if s.scenario_id == "SCEN-09-PENDING-APPROVAL-LIFECYCLE"
        )
        tamper_scen = next(
            s for s in dataset.scenarios if s.scenario_id == "SCEN-10-TAMPERED-AFTER-APPROVAL"
        )
        single_container = ScenarioDatasetContainer(
            dataset_name="approval_test",
            version="1.0.0",
            description="desc",
            disclaimer="disclaimer",
            scenarios=[app_scen, tamper_scen],
        )
        runner = ScenarioRunner(dataset=single_container)
        report = runner.run()

        assert report.passed_scenarios == 2
        app_res = report.scenario_results[0]
        assert app_res.passed is True
        assert app_res.step_results[1].actual_status == "pending_approval"
        assert app_res.step_results[2].actual_status == "approved"
        assert app_res.step_results[3].actual_status == "executed"
        assert app_res.step_results[3].actual_reason_code == "APPROVAL_CONSUMED"

        tamper_res = report.scenario_results[1]
        assert tamper_res.passed is True
        assert tamper_res.step_results[0].actual_status == "pending_approval"
        assert tamper_res.step_results[1].actual_status == "approved"
        assert tamper_res.step_results[2].actual_status == "denied"
        assert tamper_res.step_results[2].actual_reason_code == "DENY_APPROVAL_ARGUMENTS_MISMATCH"

    def test_stable_scenario_ids_and_json_report_serialization(self, tmp_path: Path) -> None:
        runner = ScenarioRunner()
        report = runner.run()

        out_file = tmp_path / "scenario_report.json"
        out_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        raw_data = json.loads(out_file.read_text(encoding="utf-8"))
        assert raw_data["benchmark_name"] == "PromptProbe Multi-Step Scenario Evaluation"
        assert raw_data["total_scenarios"] == 10
        assert raw_data["passed_scenarios"] == 10
        assert raw_data["metrics"]["unauthorized_executions"] == 0

        # Validate round-trip Pydantic reconstruction
        reconstructed = ScenarioBenchmarkReport.model_validate(raw_data)
        assert reconstructed.total_scenarios == report.total_scenarios
        assert reconstructed.metrics.scenario_success_rate == 1.0

    def test_malformed_scenario_fails_cleanly_without_crashing_run(self) -> None:
        malformed_scenario = SecurityScenario(
            scenario_id="MALFORMED-001",
            category="malformed",
            title="Malformed Step Action",
            description="Tests that single step exception is safely isolated",
            steps=[
                ScenarioStep(
                    step_id="m1",
                    step_type=ScenarioStepType.APPROVAL_DECISION,
                    # No pending approval exists, triggering error
                    approval_decision="approve",
                    expected_status="approved",
                )
            ],
        )

        dataset = load_scenario_dataset()
        augmented_scenarios = [*list(dataset.scenarios), malformed_scenario]
        container = ScenarioDatasetContainer(
            dataset_name="augmented",
            version="1.0.0",
            description="desc",
            disclaimer="disclaimer",
            scenarios=augmented_scenarios,
        )

        runner = ScenarioRunner(dataset=container)
        report = runner.run()

        # 10 valid scenarios should still pass, malformed should fail gracefully
        assert report.total_scenarios == 11
        assert report.passed_scenarios == 10
        assert report.failed_scenarios == 1
        assert len(report.failures) == 1
        assert report.failures[0]["scenario_id"] == "MALFORMED-001"


class TestScenarioCLI:
    """Tests covering PromptProbe scenario command-line interface execution."""

    def test_cli_scenarios_subcommand_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        from promptprobe.cli import main

        exit_code = main(["scenarios"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "PromptProbe Multi-Step Scenario Evaluation" in captured.out
        assert "Total Scenarios Evaluated: 10" in captured.out
        assert "Unauthorized Executions:   0" in captured.out

    def test_cli_scenarios_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from promptprobe.cli import main

        out_path = tmp_path / "scenario_artifact.json"
        exit_code = main(["scenarios", "--output", str(out_path)])
        assert exit_code == 0
        assert out_path.is_file()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["total_scenarios"] == 10

    def test_cli_run_include_scenarios(self, capsys: pytest.CaptureFixture[str]) -> None:
        from promptprobe.cli import main

        exit_code = main(["run", "--include-scenarios"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "PromptProbe Adversarial Evaluation Report" in captured.out
        assert "PromptProbe Multi-Step Scenario Evaluation" in captured.out

    def test_cli_scenarios_missing_file_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        from promptprobe.cli import main

        exit_code = main(["scenarios", "--dataset", "/tmp/non_existent_scen_9999.json"])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "Error executing PromptProbe benchmark" in captured.err
