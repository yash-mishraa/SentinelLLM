"""Unit test verifying the SentinelLLM portfolio demonstration entrypoint."""

import pytest

from sentinelllm.demo import run_demo


class TestPortfolioDemo:
    """Verifies that the portfolio demonstration executes deterministically and exits 0."""

    def test_run_demo_executes_successfully(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = run_demo()
        assert exit_code == 0

        captured = capsys.readouterr()
        # Verify all 6 stages executed
        assert "[STAGE 1]" in captured.out
        assert "Direct Prompt-Injection Defense" in captured.out
        assert "[STAGE 2]" in captured.out
        assert "Indirect Prompt-Injection Defense" in captured.out
        assert "[STAGE 3]" in captured.out
        assert "Action-Level Policy Enforcement" in captured.out
        assert "[STAGE 4]" in captured.out
        assert "Sensitive Action Approval Workflow" in captured.out
        assert "[STAGE 5]" in captured.out
        assert "Supervisor Approval & Authorized Execution" in captured.out
        assert "[STAGE 6]" in captured.out
        assert "Modified Request Rejection" in captured.out
        assert "DEMONSTRATION COMPLETE" in captured.out

    def test_cli_demo_subcommand(self, capsys: pytest.CaptureFixture[str]) -> None:
        from promptprobe.cli import main

        exit_code = main(["demo"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "DEMONSTRATION COMPLETE" in captured.out
