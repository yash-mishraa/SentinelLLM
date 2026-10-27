"""Language model adapter subsystem for SentinelLLM and PromptProbe."""

from sentinelllm.adapters.base import (
    AuthenticationError,
    BaseLLMAdapter,
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
    DEFAULT_MAX_BUDGET_USD,
    MAX_ALLOWED_BUDGET_CEILING_USD,
    BudgetTracker,
    RunBudget,
)
from sentinelllm.adapters.fake import (
    MODE_AUTH_ERROR,
    MODE_PROVIDER_ERROR,
    MODE_RATE_LIMIT,
    MODE_REFUSAL,
    MODE_STANDARD,
    MODE_TIMEOUT,
    MODE_VULNERABLE,
    FakeLLMAdapter,
)
from sentinelllm.adapters.openai import MODEL_PRICING_RATES, OpenAICompatibleAdapter

__all__ = [
    "DEFAULT_BUDGET_CEILING_USD",
    "DEFAULT_MAX_BUDGET_USD",
    "MAX_ALLOWED_BUDGET_CEILING_USD",
    "MODEL_PRICING_RATES",
    "MODE_AUTH_ERROR",
    "MODE_PROVIDER_ERROR",
    "MODE_RATE_LIMIT",
    "MODE_REFUSAL",
    "MODE_STANDARD",
    "MODE_TIMEOUT",
    "MODE_VULNERABLE",
    "AuthenticationError",
    "BaseLLMAdapter",
    "BudgetExceededError",
    "BudgetTracker",
    "FakeLLMAdapter",
    "LLMAdapterError",
    "LLMConfig",
    "LLMResponse",
    "OpenAICompatibleAdapter",
    "ProviderUnavailableError",
    "RateLimitError",
    "RunBudget",
    "SafetyOptInRequiredError",
    "TimeoutError",
]
