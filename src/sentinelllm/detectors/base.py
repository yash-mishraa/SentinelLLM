"""Base detector contract and interface for heuristic security scanners."""

from abc import ABC, abstractmethod
from typing import final

from sentinelllm.contracts.decision import SecurityFinding
from sentinelllm.contracts.messages import BaseContentItem, SecurityContent


class BaseDetector(ABC):
    """Abstract base class for deterministic security pattern scanners.

    Detectors evaluate content and emit analytical observations (`SecurityFinding`).
    Detectors are strictly observational: finding emission does NOT grant, revoke,
    or modify permissions.
    """

    @property
    @abstractmethod
    def detector_id(self) -> str:
        """Unique identifier for this detector implementation."""
        ...

    @property
    @abstractmethod
    def finding_category(self) -> str:
        """Standardized finding category emitted by this detector."""
        ...

    @abstractmethod
    def scan(self, item: SecurityContent | str) -> tuple[SecurityFinding, ...]:
        """Scan a content item or text payload for security patterns.

        Args:
            item: Either a SecurityContent object or raw text string.

        Returns:
            A tuple of standardized SecurityFinding objects. Empty if no pattern matched.

        Raises:
            TypeError: If input is neither a SecurityContent instance nor a string.
            ValueError: If input is a blank/empty string without content.
        """
        ...

    @final
    def _extract_text(self, item: SecurityContent | str) -> str:
        """Extract and validate text from supported input types."""
        if isinstance(item, BaseContentItem):
            text = item.content
        elif isinstance(item, str):
            text = item
        else:
            raise TypeError(
                f"Detector '{self.detector_id}' requires SecurityContent or str, "
                f"got {type(item).__name__}"
            )

        if not text or not text.strip():
            raise ValueError(f"Detector '{self.detector_id}' received empty content to scan.")

        return text
