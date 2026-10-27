"""Unit and integration tests for PromptProbe hybrid evaluation and CLI."""

from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from promptprobe.cli import main
from promptprobe.hybrid import HybridBenchmarkRunner
from promptprobe.hybrid_models import ModelExecutionStatus
from sentinelllm.adapters.base import SafetyOptInRequiredError
from sentinelllm.adapters.budget import BudgetTracker, RunBudget
from sentinelllm.adapters.fake import FakeLLMAdapter
from sentinelllm.api.app import create_app
from sentinelllm.api.auth import ApiKeyRegistry
from sentinelllm.api.config import ApiConfig
from sentinelllm.api.dependencies import (
    set_api_config,
    set_api_key_registry,
    set_db_config,
    set_rate_limiter,
)
from sentinelllm.api.rate_limiter import InMemoryRateLimiter
from sentinelllm.db.config import DatabaseConfig
from sentinelllm.db.models import Base


class TestHybridBenchmarkRunner:
    """Tests evaluating the dual-layer HybridBenchmarkRunner."""

    def test_offline_fake_adapter_evaluation(self) -> None:
        adapter = FakeLLMAdapter(mode="standard")
        tracker = BudgetTracker(budget=RunBudget(max_cost_usd=0.20))
        runner = HybridBenchmarkRunner(
            adapter=adapter,
            budget_tracker=tracker,
            max_cases=10,
        )
        report = runner.run()

        assert report.benchmark_name == "PromptProbe Hybrid Evaluation"
        assert report.provider == "fake"
        assert report.is_live is False
        assert len(report.case_results) == 10
        assert report.metrics.total_cases == 10
        assert report.metrics.actions_enforced_correctly >= 0

        # Gateway metrics should be valid floats/None
        if report.metrics.content_cases > 0:
            assert report.metrics.gateway_accuracy >= 0.0

        # Cost and token consumption should be tracked
        assert report.metrics.total_tokens_consumed >= 0
        assert report.metrics.total_cost_usd >= 0.0

    def test_unprotected_baseline_dispatches_attacks(self) -> None:
        adapter = FakeLLMAdapter(mode="standard")
        runner = HybridBenchmarkRunner(
            adapter=adapter,
            unprotected_baseline=True,
            max_cases=5,
        )
        report = runner.run()

        # In unprotected baseline, attacks are not blocked before LLM
        for case in report.case_results:
            if not case.is_action_case:
                assert case.model_status == ModelExecutionStatus.UNPROTECTED_DISPATCHED

    def test_budget_exhaustion_skips_subsequent_cases(self) -> None:
        # Tight budget of $0.000001
        budget = RunBudget(max_cost_usd=0.000001)
        tracker = BudgetTracker(budget=budget)
        adapter = FakeLLMAdapter(mode="standard", budget_tracker=tracker)

        runner = HybridBenchmarkRunner(
            adapter=adapter,
            budget_tracker=tracker,
            max_cases=15,
        )
        report = runner.run()

        # At least one case should be skipped due to budget exhaustion
        skipped = [
            r for r in report.case_results if r.model_status == ModelExecutionStatus.SKIPPED_BUDGET
        ]
        assert len(skipped) > 0
        assert report.metrics.budget_exhausted is True


class TestHybridCLI:
    """Tests covering PromptProbe CLI hybrid subcommands."""

    def test_cli_hybrid_fake_provider(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["hybrid", "--provider", "fake", "--max-cases", "3"])
        assert exit_code == 0
        captured = capsys.readouterr().out
        assert "PromptProbe Hybrid Evaluation Report" in captured
        assert "SENTINELLLM GATEWAY METRICS" in captured
        assert "MODEL TELEMETRY & COST EFFICIENCY" in captured

    def test_cli_hybrid_json_output(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "hybrid_report.json"
            exit_code = main(
                [
                    "hybrid",
                    "--provider",
                    "fake",
                    "--max-cases",
                    "2",
                    "--output",
                    str(out_file),
                ]
            )
            assert exit_code == 0
            assert out_file.exists()
            content = out_file.read_text(encoding="utf-8")
            assert "benchmark_name" in content
            assert "PromptProbe Hybrid Evaluation" in content

    def test_cli_hybrid_openai_requires_live_opt_in(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = main(["hybrid", "--provider", "openai"])
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "Safety guard: live LLM evaluation requires --live-opt-in" in err

    def test_run_hybrid_direct_raises_opt_in_error(self) -> None:
        from promptprobe.cli import run_hybrid

        with pytest.raises(
            SafetyOptInRequiredError,
            match="Safety guard: live LLM evaluation requires --live-opt-in",
        ):
            run_hybrid(
                provider="openai",
                model="gpt-4o-mini",
                mode="standard",
                base_url=None,
                max_budget=0.20,
                max_cases=2,
                live_opt_in=False,
                unprotected=False,
                dataset_path=None,
                output_path=None,
            )


class TestHybridAPIEndpoint:
    """Tests verifying REST Gateway hybrid summary endpoint."""

    @pytest.fixture
    def client(self, tmp_path: Path) -> Generator[TestClient, None, None]:
        db_file = tmp_path / "test_hybrid_api.db"
        db_config = DatabaseConfig(database_url=f"sqlite:///{db_file}")
        engine = create_engine(
            db_config.database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        set_db_config(db_config)

        registry = ApiKeyRegistry()
        registry.register_key(
            raw_key="test-admin-key",
            principal_id="admin_user",
            roles=["admin"],
            permissions=["*"],
        )
        set_api_key_registry(registry)
        set_rate_limiter(InMemoryRateLimiter())
        set_api_config(ApiConfig())

        app = create_app()
        yield TestClient(app)
        engine.dispose()

    def test_get_hybrid_summary_unauthorized(self, client: TestClient) -> None:
        resp = client.get("/api/v1/benchmark/hybrid/summary")
        assert resp.status_code == 401

    def test_get_hybrid_summary_authorized(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/benchmark/hybrid/summary",
            headers={"X-API-Key": "test-admin-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "supported_providers" in data
        assert "openai" in data["supported_providers"]
        assert "fake" in data["supported_providers"]
        assert "default_model" in data
        assert "pricing_rates" in data
        assert data["default_budget_ceiling_usd"] == 0.20
        assert data["max_budget_ceiling_usd"] == 1.00
        assert "features" in data
