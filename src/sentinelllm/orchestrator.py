"""Minimal synchronous request lifecycle orchestrator."""

from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sentinelllm.contracts.audit import AuditEvent
from sentinelllm.contracts.context import RequestContext


class LifecycleResult(BaseModel):
    """Structured output returned by the lifecycle orchestrator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_context: RequestContext
    audit_events: tuple[AuditEvent, ...]
    status: str
    item_count: int
    provenance_summary: dict[str, int]
    metadata: dict[str, Any] = Field(default_factory=dict)


class LifecycleOrchestrator:
    """Synchronous orchestrator coordinating early-stage request lifecycle events.

    This component establishes request correlation, validates context structure,
    and produces structured audit records without modifying content provenance.
    It intentionally does not perform security detection or policy decisions in
    this milestone.
    """

    def __init__(self, component_name: str = "lifecycle_orchestrator") -> None:
        self.component_name = component_name

    def process(self, context: RequestContext) -> LifecycleResult:
        """Process an inbound request context and produce lifecycle audit records.

        Args:
            context: Validated immutable request context.

        Returns:
            LifecycleResult containing the preserved context and emitted audit events.

        Raises:
            TypeError: If context is not an instance of RequestContext.
        """
        if not isinstance(context, RequestContext):
            raise TypeError(f"Expected RequestContext instance, got {type(context).__name__}")

        # Count provenance distribution for structured, non-leaking telemetry
        counts = Counter(item.provenance.value for item in context.items)
        provenance_summary = dict(sorted(counts.items()))

        received_event = AuditEvent(
            request_id=context.request_id,
            event_type="lifecycle.request_received",
            component=self.component_name,
            metadata={
                "item_count": len(context.items),
                "has_correlation_id": context.correlation_id is not None,
                "provenance_summary": provenance_summary,
            },
        )

        processed_event = AuditEvent(
            request_id=context.request_id,
            event_type="lifecycle.context_processed",
            component=self.component_name,
            metadata={
                "status": "accepted",
                "item_count": len(context.items),
            },
        )

        return LifecycleResult(
            request_context=context,
            audit_events=(received_event, processed_event),
            status="accepted",
            item_count=len(context.items),
            provenance_summary=provenance_summary,
        )
