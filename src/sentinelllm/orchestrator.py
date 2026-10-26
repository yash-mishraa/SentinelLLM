"""Synchronous request lifecycle orchestrator integrating detector passes."""

from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sentinelllm.contracts.audit import AuditEvent
from sentinelllm.contracts.context import RequestContext
from sentinelllm.contracts.decision import SecurityFinding
from sentinelllm.detectors.registry import DetectorRegistry


class LifecycleResult(BaseModel):
    """Structured output returned by the lifecycle orchestrator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    request_context: RequestContext
    audit_events: tuple[AuditEvent, ...]
    status: str
    item_count: int
    provenance_summary: dict[str, int]
    findings: tuple[SecurityFinding, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LifecycleOrchestrator:
    """Synchronous orchestrator coordinating request lifecycle events and detector passes.

    Preserves context provenance, runs configured heuristic detectors, and produces
    privacy-safe structured audit records. Findings are strictly observational
    and do not autonomously enforce authorization decisions.
    """

    def __init__(
        self,
        component_name: str = "lifecycle_orchestrator",
        registry: DetectorRegistry | None = None,
    ) -> None:
        self.component_name = component_name
        self.registry = registry if registry is not None else DetectorRegistry()

    def process(self, context: RequestContext) -> LifecycleResult:
        """Process an inbound request context, execute configured detectors, and audit outcomes.

        Args:
            context: Validated immutable request context.

        Returns:
            LifecycleResult containing preserved context, emitted audit events, and findings.

        Raises:
            TypeError: If context is not an instance of RequestContext.
        """
        if not isinstance(context, RequestContext):
            raise TypeError(f"Expected RequestContext instance, got {type(context).__name__}")

        # Compute provenance distribution for structured, non-leaking telemetry
        counts = Counter(item.provenance.value for item in context.items)
        provenance_summary = dict(sorted(counts.items()))

        audit_events: list[AuditEvent] = []

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
        audit_events.append(received_event)

        # Execute configured detectors across context items
        findings = self.registry.scan_context(context)

        if findings:
            categories = sorted({f.category for f in findings})
            findings_event = AuditEvent(
                request_id=context.request_id,
                event_type="lifecycle.findings_detected",
                component=self.component_name,
                metadata={
                    "finding_count": len(findings),
                    "categories": categories,
                },
            )
            audit_events.append(findings_event)

        processed_event = AuditEvent(
            request_id=context.request_id,
            event_type="lifecycle.context_processed",
            component=self.component_name,
            metadata={
                "status": "accepted",
                "item_count": len(context.items),
                "finding_count": len(findings),
            },
        )
        audit_events.append(processed_event)

        return LifecycleResult(
            request_context=context,
            audit_events=tuple(audit_events),
            status="accepted",
            item_count=len(context.items),
            provenance_summary=provenance_summary,
            findings=findings,
        )
