"""Cost and resource control subsystem for live LLM evaluations."""

import threading
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sentinelllm.adapters.base import BudgetExceededError

# Conservative safety ceilings
MAX_ALLOWED_BUDGET_CEILING_USD = 1.00  # Hard absolute ceiling for any evaluation run
DEFAULT_MAX_BUDGET_USD = 0.20  # Default budget ceiling ($0.20)
DEFAULT_BUDGET_CEILING_USD = DEFAULT_MAX_BUDGET_USD
DEFAULT_MAX_REQUESTS = 30  # Default max requests per run
DEFAULT_MAX_TOTAL_TOKENS = 25_000  # Default max tokens per run
DEFAULT_MAX_WALL_CLOCK_SECONDS = 120.0  # Default max runtime in seconds


class RunBudget(BaseModel):
    """Immutable bounds defining financial and computational constraints for a run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_cost_usd: float = Field(
        default=DEFAULT_MAX_BUDGET_USD,
        gt=0.0,
        le=MAX_ALLOWED_BUDGET_CEILING_USD,
        description="Maximum permitted financial cost in USD before terminating run",
    )
    max_requests: int = Field(
        default=DEFAULT_MAX_REQUESTS,
        ge=1,
        le=500,
        description="Maximum number of model calls permitted during the run",
    )
    max_total_tokens: int = Field(
        default=DEFAULT_MAX_TOTAL_TOKENS,
        ge=100,
        le=200_000,
        description="Maximum cumulative tokens (prompt + completion) permitted",
    )
    max_wall_clock_seconds: float = Field(
        default=DEFAULT_MAX_WALL_CLOCK_SECONDS,
        ge=5.0,
        le=600.0,
        description="Maximum cumulative elapsed wall-clock seconds permitted",
    )


class BudgetTracker:
    """Thread-safe tracker enforcing execution limits and preventing cost overruns."""

    def __init__(self, budget: RunBudget | None = None) -> None:
        self.budget = budget if budget is not None else RunBudget()
        self._lock = threading.Lock()
        self._requests_count = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._total_cost_usd = 0.0
        self._start_time = time.perf_counter()

    @property
    def total_tokens(self) -> int:
        with self._lock:
            return self._prompt_tokens + self._completion_tokens

    @property
    def total_cost(self) -> float:
        with self._lock:
            return self._total_cost_usd

    @property
    def requests_count(self) -> int:
        with self._lock:
            return self._requests_count

    def check_preflight(
        self,
        estimated_prompt_tokens: int,
        estimated_completion_tokens: int,
        cost_estimator: Callable[[int, int], float],
    ) -> None:
        """Validate whether a proposed request can proceed without breaching budget constraints.

        Raises:
            BudgetExceededError: If the request exceeds financial, token, or time limits.
        """
        with self._lock:
            # 1. Check elapsed wall-clock duration
            elapsed = time.perf_counter() - self._start_time
            if elapsed > self.budget.max_wall_clock_seconds:
                raise BudgetExceededError(
                    f"Wall-clock runtime limit exceeded: elapsed {elapsed:.1f}s > "
                    f"limit {self.budget.max_wall_clock_seconds:.1f}s."
                )

            # 2. Check request count limit
            if self._requests_count >= self.budget.max_requests:
                raise BudgetExceededError(
                    f"Maximum requests limit reached: {self._requests_count} >= "
                    f"limit {self.budget.max_requests}."
                )

            # 3. Check token limits
            est_tokens = (
                self._prompt_tokens
                + self._completion_tokens
                + estimated_prompt_tokens
                + estimated_completion_tokens
            )
            if est_tokens > self.budget.max_total_tokens:
                raise BudgetExceededError(
                    f"Projected token consumption ({est_tokens}) would exceed limit "
                    f"({self.budget.max_total_tokens} tokens)."
                )

            # 4. Check cost limit
            projected_cost = cost_estimator(estimated_prompt_tokens, estimated_completion_tokens)
            if (self._total_cost_usd + projected_cost) > self.budget.max_cost_usd:
                raise BudgetExceededError(
                    f"Projected cost (${self._total_cost_usd + projected_cost:.4f}) would exceed "
                    f"configured budget limit (${self.budget.max_cost_usd:.4f})."
                )

    def record_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        """Record actual tokens and cost consumed by an executed request."""
        with self._lock:
            self._requests_count += 1
            self._prompt_tokens += max(0, prompt_tokens)
            self._completion_tokens += max(0, completion_tokens)
            self._total_cost_usd += max(0.0, cost_usd)

    def get_summary(self) -> dict[str, Any]:
        """Return a snapshot of current budget consumption."""
        with self._lock:
            elapsed = time.perf_counter() - self._start_time
            return {
                "requests_count": self._requests_count,
                "max_requests": self.budget.max_requests,
                "prompt_tokens": self._prompt_tokens,
                "completion_tokens": self._completion_tokens,
                "total_tokens": self._prompt_tokens + self._completion_tokens,
                "max_total_tokens": self.budget.max_total_tokens,
                "total_cost_usd": round(self._total_cost_usd, 6),
                "max_cost_usd": self.budget.max_cost_usd,
                "elapsed_seconds": round(elapsed, 2),
                "max_wall_clock_seconds": self.budget.max_wall_clock_seconds,
            }
