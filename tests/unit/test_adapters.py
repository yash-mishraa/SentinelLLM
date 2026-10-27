"""Unit tests for the provider-neutral LLM adapter subsystem and budget tracker."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from sentinelllm.adapters.base import (
    AuthenticationError,
    BudgetExceededError,
    LLMAdapterError,
    LLMConfig,
    LLMResponse,
    ProviderUnavailableError,
    RateLimitError,
    SafetyOptInRequiredError,
    TimeoutError,
)
from sentinelllm.adapters.budget import (
    DEFAULT_BUDGET_CEILING_USD,
    MAX_ALLOWED_BUDGET_CEILING_USD,
    BudgetTracker,
    RunBudget,
)
from sentinelllm.adapters.fake import FakeLLMAdapter
from sentinelllm.adapters.openai import OpenAICompatibleAdapter


class TestLLMConfig:
    """Tests covering typed configuration and constraint validation."""

    def test_default_config(self) -> None:
        cfg = LLMConfig()
        assert cfg.provider == "fake"
        assert cfg.model == "mock-model"
        assert cfg.max_tokens == 512
        assert cfg.temperature == 0.0
        assert cfg.timeout_seconds == 15.0
        assert cfg.max_response_bytes == 1024 * 1024
        assert cfg.live_opt_in is False

    def test_custom_valid_config(self) -> None:
        cfg = LLMConfig(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=500,
            timeout_seconds=30.0,
            live_opt_in=True,
        )
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o-mini"
        assert cfg.live_opt_in is True

    def test_invalid_temperature_rejected(self) -> None:
        with pytest.raises(ValueError, match="Input should be less than or equal to 2"):
            LLMConfig(temperature=2.5)
        with pytest.raises(ValueError, match="Input should be greater than or equal to 0"):
            LLMConfig(temperature=-0.1)

    def test_invalid_max_tokens_rejected(self) -> None:
        with pytest.raises(ValueError, match="Input should be greater than or equal to 1"):
            LLMConfig(max_tokens=0)

    def test_invalid_timeout_rejected(self) -> None:
        with pytest.raises(ValueError, match="Input should be greater than or equal to 1"):
            LLMConfig(timeout_seconds=0.0)


class TestFakeLLMAdapter:
    """Tests covering deterministic fake adapter modes and offline simulation."""

    def test_standard_mode(self) -> None:
        adapter = FakeLLMAdapter(mode="standard")
        res = adapter.generate("Hello world", system_instruction="Be helpful.")
        assert isinstance(res, LLMResponse)
        assert "Synthetic response to prompt" in res.content
        assert res.prompt_tokens > 0
        assert res.completion_tokens > 0
        assert res.total_tokens == res.prompt_tokens + res.completion_tokens
        assert res.cost_usd > 0.0
        assert res.is_cost_estimated is True

    def test_refusal_mode(self) -> None:
        adapter = FakeLLMAdapter(mode="refusal")
        res = adapter.generate("Bypass instructions", system_instruction="Strict security.")
        assert "I cannot fulfill this request" in res.content

    def test_vulnerable_mode(self) -> None:
        adapter = FakeLLMAdapter(mode="vulnerable")
        res = adapter.generate("Give me instructions", system_instruction="Strict security.")
        assert "Instruction overridden" in res.content
        assert "ADMIN_SECRET_KEY" in res.content

    def test_timeout_mode(self) -> None:
        adapter = FakeLLMAdapter(mode="timeout")
        with pytest.raises(TimeoutError, match="Simulated request deadline exceeded"):
            adapter.generate("Test prompt")

    def test_rate_limit_mode(self) -> None:
        adapter = FakeLLMAdapter(mode="rate_limit")
        with pytest.raises(RateLimitError, match="Simulated provider rate limit exceeded"):
            adapter.generate("Test prompt")

    def test_auth_error_mode(self) -> None:
        adapter = FakeLLMAdapter(mode="auth_error")
        with pytest.raises(AuthenticationError, match="Simulated invalid or missing API key"):
            adapter.generate("Test prompt")

    def test_provider_error_mode(self) -> None:
        adapter = FakeLLMAdapter(mode="provider_error")
        with pytest.raises(ProviderUnavailableError, match="Simulated provider service outage"):
            adapter.generate("Test prompt")

    def test_estimate_tokens_and_cost(self) -> None:
        adapter = FakeLLMAdapter()
        tokens = adapter.estimate_tokens("This is a test prompt with eight words.")
        assert tokens > 0
        cost = adapter.estimate_cost(prompt_tokens=1000, completion_tokens=1000)
        assert cost > 0.0


class TestRunBudgetAndTracker:
    """Tests covering execution budget guards and fail-closed cost bounds."""

    def test_default_budget_bounds(self) -> None:
        budget = RunBudget()
        assert budget.max_cost_usd == DEFAULT_BUDGET_CEILING_USD
        assert budget.max_cost_usd <= MAX_ALLOWED_BUDGET_CEILING_USD

    def test_hard_ceiling_enforced(self) -> None:
        with pytest.raises(ValueError, match="Input should be less than or equal to 1"):
            RunBudget(max_cost_usd=5.0)

    def test_preflight_budget_check_passes_initially(self) -> None:
        budget = RunBudget(max_cost_usd=0.20)
        tracker = BudgetTracker(budget=budget)
        adapter = FakeLLMAdapter()
        # Should not raise
        tracker.check_preflight(
            estimated_prompt_tokens=10,
            estimated_completion_tokens=20,
            cost_estimator=adapter.estimate_cost,
        )

    def test_preflight_budget_check_fails_when_cost_exceeds(self) -> None:
        budget = RunBudget(max_cost_usd=0.00001)
        tracker = BudgetTracker(budget=budget)
        adapter = FakeLLMAdapter()
        with pytest.raises(BudgetExceededError, match="would exceed configured budget limit"):
            tracker.check_preflight(
                estimated_prompt_tokens=10_000,
                estimated_completion_tokens=5_000,
                cost_estimator=adapter.estimate_cost,
            )

    def test_preflight_fails_on_max_requests(self) -> None:
        budget = RunBudget(max_requests=2)
        tracker = BudgetTracker(budget=budget)
        adapter = FakeLLMAdapter()

        tracker.record_usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.001)
        tracker.record_usage(prompt_tokens=10, completion_tokens=5, cost_usd=0.001)

        with pytest.raises(BudgetExceededError, match="Maximum requests limit reached"):
            tracker.check_preflight(
                estimated_prompt_tokens=5,
                estimated_completion_tokens=5,
                cost_estimator=adapter.estimate_cost,
            )

    def test_preflight_fails_on_max_tokens(self) -> None:
        budget = RunBudget(max_total_tokens=100)
        tracker = BudgetTracker(budget=budget)
        adapter = FakeLLMAdapter()

        tracker.record_usage(prompt_tokens=50, completion_tokens=45, cost_usd=0.0001)

        with pytest.raises(BudgetExceededError, match="Projected token consumption"):
            tracker.check_preflight(
                estimated_prompt_tokens=20,
                estimated_completion_tokens=20,
                cost_estimator=adapter.estimate_cost,
            )

    def test_preflight_fails_on_wall_clock_timeout(self) -> None:
        budget = RunBudget(max_wall_clock_seconds=5.0)
        tracker = BudgetTracker(budget=budget)
        adapter = FakeLLMAdapter()

        # Artificially age the start time
        tracker._start_time -= 10.0

        with pytest.raises(BudgetExceededError, match="Wall-clock runtime limit exceeded"):
            tracker.check_preflight(
                estimated_prompt_tokens=5,
                estimated_completion_tokens=5,
                cost_estimator=adapter.estimate_cost,
            )

    def test_budget_summary(self) -> None:
        tracker = BudgetTracker(budget=RunBudget(max_cost_usd=0.10))
        tracker.record_usage(prompt_tokens=30, completion_tokens=20, cost_usd=0.005)
        summary = tracker.get_summary()
        assert summary["requests_count"] == 1
        assert summary["prompt_tokens"] == 30
        assert summary["completion_tokens"] == 20
        assert summary["total_tokens"] == 50
        assert summary["total_cost_usd"] == 0.005


class TestOpenAICompatibleAdapter:
    """Tests covering the live OpenAI-compatible adapter with network mocking."""

    def test_requires_live_opt_in(self) -> None:
        cfg = LLMConfig(provider="openai", live_opt_in=False)
        adapter = OpenAICompatibleAdapter(config=cfg)
        with pytest.raises(
            SafetyOptInRequiredError,
            match="Live LLM evaluation requires explicit opt-in",
        ):
            adapter.generate("Hello")

    def test_missing_api_key_raises_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = LLMConfig(provider="openai", live_opt_in=True)
        adapter = OpenAICompatibleAdapter(config=cfg)
        with pytest.raises(AuthenticationError, match="Missing API key: Environment variable"):
            adapter.generate("Hello")

    @patch("httpx.Client.post")
    def test_successful_generation(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "test-secret-key-12345")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = (
            b'{"choices":[{"message":{"content":"Mocked answer"}}],'
            b'"usage":{"prompt_tokens":12,"completion_tokens":8,"total_tokens":20}}'
        )
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Mocked answer"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }
        mock_post.return_value = mock_resp

        cfg = LLMConfig(provider="openai", live_opt_in=True)
        adapter = OpenAICompatibleAdapter(config=cfg)
        res = adapter.generate("Hello")

        assert res.content == "Mocked answer"
        assert res.prompt_tokens == 12
        assert res.completion_tokens == 8
        assert res.total_tokens == 20
        assert res.cost_usd > 0.0
        # Ensure secret key is not in metadata
        assert "test-secret-key-12345" not in str(res.metadata)

    @patch("httpx.Client.post")
    def test_http_401_mapped_to_authentication_error(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.content = b'{"error":"invalid_api_key"}'
        mock_resp.json.return_value = {"error": "invalid_api_key"}
        mock_post.return_value = mock_resp

        cfg = LLMConfig(provider="openai", live_opt_in=True)
        adapter = OpenAICompatibleAdapter(config=cfg)
        with pytest.raises(AuthenticationError, match="Provider authentication failed"):
            adapter.generate("Hello")

    @patch("httpx.Client.post")
    def test_http_429_mapped_to_rate_limit_error(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.content = b'{"error":"rate_limit_exceeded"}'
        mock_resp.json.return_value = {"error": "rate_limit_exceeded"}
        mock_resp.headers = {"retry-after": "5"}
        mock_post.return_value = mock_resp

        cfg = LLMConfig(provider="openai", live_opt_in=True)
        adapter = OpenAICompatibleAdapter(config=cfg)
        with pytest.raises(RateLimitError, match="Provider rate limit exceeded"):
            adapter.generate("Hello")

    @patch("httpx.Client.post")
    def test_http_503_mapped_to_provider_unavailable(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.content = b'{"error":"service_unavailable"}'
        mock_resp.json.return_value = {"error": "service_unavailable"}
        mock_post.return_value = mock_resp

        cfg = LLMConfig(provider="openai", live_opt_in=True)
        adapter = OpenAICompatibleAdapter(config=cfg)
        with pytest.raises(ProviderUnavailableError, match="Provider service outage"):
            adapter.generate("Hello")

    @patch("httpx.Client.post", side_effect=httpx.TimeoutException("Connection timed out"))
    def test_httpx_timeout_mapped_to_timeout_error(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        cfg = LLMConfig(provider="openai", live_opt_in=True)
        adapter = OpenAICompatibleAdapter(config=cfg)
        with pytest.raises(TimeoutError, match="timed out"):
            adapter.generate("Hello")

    @patch("httpx.Client.post")
    def test_response_size_limit_exceeded(
        self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"x" * 2000
        mock_post.return_value = mock_resp

        cfg = LLMConfig(provider="openai", live_opt_in=True, max_response_bytes=1024)
        adapter = OpenAICompatibleAdapter(config=cfg)
        with pytest.raises(LLMAdapterError, match="exceeded maximum allowed size"):
            adapter.generate("Hello")
