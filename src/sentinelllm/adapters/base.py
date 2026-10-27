"""Provider-neutral LLM adapter interfaces, configuration, and data contracts."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMAdapterError(Exception):
    """Base exception for all LLM adapter operations."""


class AuthenticationError(LLMAdapterError):
    """Raised when provider authentication fails (e.g. invalid or missing API key)."""


class RateLimitError(LLMAdapterError):
    """Raised when provider throttles or rate limits requests."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class TimeoutError(LLMAdapterError):
    """Raised when a provider request exceeds the bounded timeout."""


class ProviderUnavailableError(LLMAdapterError):
    """Raised when a provider experiences outages, gateway errors, or 5xx responses."""


class SafetyOptInRequiredError(LLMAdapterError):
    """Raised when a live network call is attempted without explicit opt-in confirmation."""


class BudgetExceededError(LLMAdapterError):
    """Raised when evaluating a request would exceed configured cost or token limits."""


class LLMConfig(BaseModel):
    """Immutable configuration for an LLM provider adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(default="fake", description="Provider identifier (e.g. 'fake', 'openai')")
    model: str = Field(default="mock-model", description="Model identifier (e.g. 'gpt-4o-mini')")
    max_tokens: int = Field(default=512, ge=1, le=4096, description="Maximum completion tokens")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature")
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=120.0, description="Request timeout")
    max_response_bytes: int = Field(default=1024 * 1024, ge=1024, description="Max response size")
    api_key_env_var: str = Field(
        default="OPENAI_API_KEY", description="Environment variable holding the secret key"
    )
    base_url: str | None = Field(
        default=None, description="Optional custom base URL for compatible endpoints (e.g. Ollama)"
    )
    live_opt_in: bool = Field(
        default=False, description="Explicit opt-in required before executing live network calls"
    )


class LLMResponse(BaseModel):
    """Structured response returned by an LLM adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str = Field(description="Generated text response from the model")
    prompt_tokens: int = Field(ge=0, description="Tokens in the prompt")
    completion_tokens: int = Field(ge=0, description="Tokens in the generated completion")
    total_tokens: int = Field(ge=0, description="Total tokens consumed")
    latency_ms: float = Field(ge=0.0, description="Round-trip invocation latency in milliseconds")
    model: str = Field(description="Model identifier that produced the response")
    provider: str = Field(description="Provider identifier")
    cost_usd: float = Field(ge=0.0, description="Financial cost in USD (reported or estimated)")
    is_cost_estimated: bool = Field(
        default=True,
        description="True if calculated from pricing tables, False if provider-reported",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Redacted operational telemetry (never raw secrets)"
    )


class BaseLLMAdapter(ABC):
    """Abstract interface governing language model adapters.

    Security Invariants:
    1. Adapter instances must never store raw API keys or passwords on their instances
       or in returned response objects.
    2. Network calls must be bounded by explicit timeouts and response body byte limits.
    3. Failures (timeouts, 401s, 429s) must raise explicit typed exceptions, never silent fallbacks.
    4. Model responses are treated as untrusted data and can never modify policy decisions.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> LLMResponse:
        """Submit a prompt and return a structured LLM response.

        Args:
            prompt: Untrusted prompt text or test case content.
            system_instruction: Optional system instruction prompt.

        Returns:
            Structured LLMResponse detailing content, tokens, latency, and cost.

        Raises:
            AuthenticationError: On invalid or missing API keys.
            RateLimitError: On provider rate limiting / throttling.
            TimeoutError: On request deadline exceeded.
            ProviderUnavailableError: On provider outages (5xx).
            BudgetExceededError: On run budget violations.
            SafetyOptInRequiredError: If live network calls are attempted without opt-in.
        """

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string using a lightweight heuristic."""

    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate estimated cost in USD based on published model pricing rates."""
