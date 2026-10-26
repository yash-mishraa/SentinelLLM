"""Detector registry coordinating multiple configured heuristic scanners."""

from collections.abc import Sequence

from sentinelllm.contracts.context import RequestContext
from sentinelllm.contracts.decision import SecurityFinding
from sentinelllm.contracts.messages import SecurityContent
from sentinelllm.detectors.base import BaseDetector
from sentinelllm.detectors.extraction import InstructionExtractionDetector
from sentinelllm.detectors.injection import InjectionPatternDetector


class DetectorRegistry:
    """Registry coordinating the execution of configured security detectors.

    Executes detectors in registration order and returns deterministic, aggregated
    findings across scanned content items.
    """

    def __init__(self, detectors: Sequence[BaseDetector] | None = None) -> None:
        if detectors is None:
            # Default heuristic suite
            self._detectors: list[BaseDetector] = [
                InjectionPatternDetector(),
                InstructionExtractionDetector(),
            ]
        else:
            self._detectors = list(detectors)

    @property
    def detectors(self) -> tuple[BaseDetector, ...]:
        """Return registered detectors as an immutable tuple."""
        return tuple(self._detectors)

    def register(self, detector: BaseDetector) -> None:
        """Register a new detector into the scanning suite."""
        if not isinstance(detector, BaseDetector):
            raise TypeError(f"Expected BaseDetector instance, got {type(detector).__name__}")
        self._detectors.append(detector)

    def scan_item(self, item: SecurityContent | str) -> tuple[SecurityFinding, ...]:
        """Execute all registered detectors against a single content item."""
        aggregated: list[SecurityFinding] = []
        for detector in self._detectors:
            findings = detector.scan(item)
            aggregated.extend(findings)
        return tuple(aggregated)

    def scan_context(self, context: RequestContext) -> tuple[SecurityFinding, ...]:
        """Execute all registered detectors across all items in a RequestContext.

        Findings are aggregated deterministically by item order, then detector order.
        """
        if not isinstance(context, RequestContext):
            raise TypeError(f"Expected RequestContext instance, got {type(context).__name__}")

        aggregated: list[SecurityFinding] = []
        for index, item in enumerate(context.items):
            for detector in self._detectors:
                findings = detector.scan(item)
                # Augment finding metadata with item index for provenance tracking
                for finding in findings:
                    enhanced_meta = dict(finding.metadata)
                    enhanced_meta["item_index"] = index
                    enhanced_meta["item_provenance"] = item.provenance.value
                    aggregated.append(
                        SecurityFinding(
                            category=finding.category,
                            severity=finding.severity,
                            source=finding.source,
                            explanation=finding.explanation,
                            metadata=enhanced_meta,
                        )
                    )

        return tuple(aggregated)
