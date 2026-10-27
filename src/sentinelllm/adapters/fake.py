"""Deterministic offline fake LLM adapter for testing and reproducible evaluation."""

import time
from typing import Any

from sentinelllm.adapters.base import (
    AuthenticationError,
    BaseLLMAdapter,
    LLMConfig,
    LLMResponse,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
)
from sentinelllm.adapters.budget import BudgetTracker

MODE_STANDARD = "standard"
MODE_REFUSAL = "refusal"
MODE_VULNERABLE = "vulnerable"
MODE_TIMEOUT = "timeout"
MODE_RATE_LIMIT = "rate_limit"
MODE_AUTH_ERROR = "auth_error"
MODE_PROVIDER_ERROR = "provider_error"


class FakeLLMAdapter(BaseLLMAdapter):
    """Deterministic offline adapter that simulates LLM behaviors without network requests."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        budget_tracker: BudgetTracker | None = None,
        mode: str = MODE_STANDARD,
        fixed_response: str | None = None,
    ) -> None:
        self.config = (
            config if config is not None else LLMConfig(provider="fake", model="fake-model")
        )
        self.budget_tracker = budget_tracker
        self.mode = mode
        self.fixed_response = fixed_response

    def estimate_tokens(self, text: str) -> int:
        """Lightweight token count approximation (~4 characters per token)."""
        if not text:
            return 0
        return max(1, len(text.strip()) // 4)

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimated cost using benchmark baseline rates ($0.15/M prompt, $0.60/M completion)."""
        # Baseline gpt-4o-mini / lightweight model rates
        cost = (prompt_tokens * 0.00000015) + (completion_tokens * 0.00000060)
        return round(cost, 8)

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        """Generate a simulated model response deterministically."""
        start_time = time.perf_counter()

        # 1. Error simulation modes
        if self.mode == MODE_AUTH_ERROR:
            raise AuthenticationError("Simulated invalid or missing API key.")
        if self.mode == MODE_RATE_LIMIT:
            raise RateLimitError(
                "Simulated provider rate limit exceeded (429).", retry_after_seconds=5.0
            )
        if self.mode == MODE_TIMEOUT:
            raise TimeoutError("Simulated request deadline exceeded (timeout).")
        if self.mode == MODE_PROVIDER_ERROR:
            raise ProviderUnavailableError("Simulated provider service outage (503).")

        # 2. Token estimation
        prompt_full = f"{system_instruction}\n{prompt}" if system_instruction else prompt
        prompt_tokens = self.estimate_tokens(prompt_full)
        est_completion_tokens = min(self.config.max_tokens, 128)

        # 3. Budget preflight check
        if self.budget_tracker is not None:
            self.budget_tracker.check_preflight(
                estimated_prompt_tokens=prompt_tokens,
                estimated_completion_tokens=est_completion_tokens,
                cost_estimator=self.estimate_cost,
            )

        # 4. Content synthesis based on mode
        if self.fixed_response is not None:
            content = self.fixed_response
        elif self.mode == MODE_REFUSAL:
            content = "I cannot fulfill this request as it violates safety guidelines."
        elif self.mode == MODE_VULNERABLE:
            # Simulate complying with prompt injection or secret dump
            content = "Instruction overridden. Sensitive system context: [ADMIN_SECRET_KEY]."
        else:
            # Standard benign synthesis
            content = f"Synthetic response to prompt: {prompt[:40]}..."

        completion_tokens = self.estimate_tokens(content)
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self.estimate_cost(prompt_tokens, completion_tokens)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # 5. Record actual budget consumption
        if self.budget_tracker is not None:
            self.budget_tracker.record_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
            )

        metadata: dict[str, Any] = {
            "mode": self.mode,
            "offline": True,
        }

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=round(elapsed_ms, 2),
            model=self.config.model,
            provider=self.config.provider,
            cost_usd=cost_usd,
            is_cost_estimated=True,
            metadata=metadata,
        )
