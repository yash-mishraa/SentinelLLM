"""Live LLM adapter supporting OpenAI and OpenAI-compatible Chat Completion APIs."""

import os
import time
from typing import Any

import httpx

from sentinelllm.adapters.base import (
    AuthenticationError,
    BaseLLMAdapter,
    LLMAdapterError,
    LLMConfig,
    LLMResponse,
    ProviderUnavailableError,
    RateLimitError,
    SafetyOptInRequiredError,
    TimeoutError,
)
from sentinelllm.adapters.budget import BudgetTracker

# Published standard pricing benchmarks per 1,000,000 tokens (USD)
# Models not in table use conservative baseline rates (gpt-4o-mini rates)
MODEL_PRICING_RATES: dict[str, tuple[float, float]] = {
    # model_name: (prompt_cost_per_million, completion_cost_per_million)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-5-sonnet": (3.00, 15.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
}


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """Adapter for OpenAI and OpenAI-compatible endpoints (Ollama, vLLM, Groq, Together).

    Security Invariants:
    1. Requires explicit opt-in (config.live_opt_in=True) before sending network packets.
    2. API keys are resolved strictly from the specified environment variable at call time.
       Keys are never stored on the adapter instance, in response metadata, or logged.
    3. HTTP transactions are constrained by explicit timeouts and response size bounds.
    4. Provider errors (401, 429, 5xx, timeouts) map to typed exceptions without fallback.
    """

    def __init__(
        self,
        config: LLMConfig,
        budget_tracker: BudgetTracker | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.budget_tracker = budget_tracker
        self._external_client = http_client

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string (~4 characters per token heuristic)."""
        if not text:
            return 0
        return max(1, len(text.strip()) // 4)

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost in USD based on model pricing tables."""
        model_key = self.config.model.lower().strip()
        rates = MODEL_PRICING_RATES.get(model_key, (0.15, 0.60))
        prompt_cost = (prompt_tokens / 1_000_000.0) * rates[0]
        completion_cost = (completion_tokens / 1_000_000.0) * rates[1]
        return round(prompt_cost + completion_cost, 8)

    def _resolve_api_key(self) -> str:
        """Resolve API key from environment variable, failing closed if missing or empty."""
        env_var = self.config.api_key_env_var
        key = os.getenv(env_var, "").strip()
        if not key:
            raise AuthenticationError(
                f"Missing API key: Environment variable '{env_var}' is not set or empty. "
                f"Configure '{env_var}' or use offline FakeLLMAdapter."
            )
        return key

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        """Execute a chat completion request against the configured provider."""
        # 1. Safety Opt-In Verification
        if not self.config.live_opt_in:
            raise SafetyOptInRequiredError(
                "Live LLM evaluation requires explicit opt-in confirmation. "
                "Set live_opt_in=True on LLMConfig or pass --live-opt-in on the CLI."
            )

        # 2. Resolve credentials
        api_key = self._resolve_api_key()

        # 3. Budget preflight check
        prompt_full = f"{system_instruction}\n{prompt}" if system_instruction else prompt
        estimated_prompt_tokens = self.estimate_tokens(prompt_full)
        estimated_completion_tokens = min(self.config.max_tokens, 256)

        if self.budget_tracker is not None:
            self.budget_tracker.check_preflight(
                estimated_prompt_tokens=estimated_prompt_tokens,
                estimated_completion_tokens=estimated_completion_tokens,
                cost_estimator=self.estimate_cost,
            )

        # 4. Construct request payload
        base_endpoint = (
            self.config.base_url.rstrip("/")
            if self.config.base_url
            else "https://api.openai.com/v1"
        )
        url = f"{base_endpoint}/chat/completions"

        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "SentinelLLM-PromptProbe/0.1.0",
        }

        # 5. Dispatch bounded HTTP request
        client = self._external_client if self._external_client is not None else httpx.Client()
        close_client = self._external_client is None
        start_time = time.perf_counter()

        try:
            resp = client.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Check response size boundary
            if len(resp.content) > self.config.max_response_bytes:
                raise LLMAdapterError(
                    f"Response body exceeded maximum allowed size of "
                    f"{self.config.max_response_bytes} bytes."
                )

            # Map status codes to typed exceptions
            if resp.status_code == 401:
                raise AuthenticationError(
                    "Provider authentication failed (HTTP 401). Verify your API key credential."
                )
            if resp.status_code == 429:
                retry_after_str = resp.headers.get("retry-after")
                retry_after = (
                    float(retry_after_str)
                    if retry_after_str and retry_after_str.isdigit()
                    else None
                )
                raise RateLimitError(
                    "Provider rate limit exceeded (HTTP 429).", retry_after_seconds=retry_after
                )
            if resp.status_code >= 500:
                raise ProviderUnavailableError(
                    f"Provider service outage or gateway error (HTTP {resp.status_code})."
                )
            if resp.status_code != 200:
                raise LLMAdapterError(
                    f"Provider returned unexpected error status {resp.status_code}: "
                    f"{resp.text[:200]}"
                )

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMAdapterError("Provider response missing 'choices' completion array.")

            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", estimated_prompt_tokens)
            completion_tokens = usage.get("completion_tokens", self.estimate_tokens(content))
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

            cost_usd = self.estimate_cost(prompt_tokens, completion_tokens)

            # 6. Record budget consumption
            if self.budget_tracker is not None:
                self.budget_tracker.record_usage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost_usd,
                )

            metadata: dict[str, Any] = {
                "finish_reason": choices[0].get("finish_reason"),
                "system_fingerprint": data.get("system_fingerprint"),
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

        except httpx.TimeoutException as err:
            raise TimeoutError(
                f"Provider request to '{url}' timed out after "
                f"{self.config.timeout_seconds} seconds."
            ) from err
        except httpx.RequestError as err:
            raise ProviderUnavailableError(
                f"Provider connection failed to '{url}': {type(err).__name__}"
            ) from err
        finally:
            if close_client:
                client.close()
