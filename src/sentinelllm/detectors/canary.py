"""Deterministic exposure monitor for configured synthetic canary tokens."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from sentinelllm.contracts.decision import SecurityFinding, Severity
from sentinelllm.contracts.messages import SecurityContent
from sentinelllm.detectors.base import BaseDetector

_MIN_CANARY_LENGTH = 8


@dataclass(frozen=True, slots=True)
class CanaryConfig:
    """Configuration for an explicitly registered synthetic canary token."""

    canary_id: str
    canary_value: str
    case_sensitive: bool = True

    def __post_init__(self) -> None:
        if not self.canary_id or not self.canary_id.strip():
            raise ValueError("CanaryConfig requires a non-empty canary_id.")
        if not self.canary_value or len(self.canary_value.strip()) < _MIN_CANARY_LENGTH:
            raise ValueError(
                f"CanaryConfig '{self.canary_id}' requires a canary_value of at least "
                f"{_MIN_CANARY_LENGTH} characters to prevent accidental collisions."
            )

    @property
    def safe_fingerprint(self) -> str:
        """Produce a safe truncated hash fingerprint without revealing the secret value."""
        digest = hashlib.sha256(self.canary_value.encode("utf-8")).hexdigest()
        return f"sha256:{digest[:8]}"


class CanaryLeakDetector(BaseDetector):
    """Monitors content for the presence of configured synthetic canary strings.

    Security Invariant:
    This monitor never logs or includes raw canary values in findings or audit
    metadata. It references matches strictly via `canary_id` and `safe_fingerprint`.
    """

    def __init__(
        self,
        canaries: Sequence[CanaryConfig],
        detector_id: str = "canary_leak_detector",
    ) -> None:
        if not canaries:
            raise ValueError("CanaryLeakDetector requires at least one configured CanaryConfig.")

        self._canaries = tuple(canaries)
        self._detector_id = detector_id

    @property
    def detector_id(self) -> str:
        return self._detector_id

    @property
    def finding_category(self) -> str:
        return "canary_leak"

    def scan(self, item: SecurityContent | str) -> tuple[SecurityFinding, ...]:
        """Scan content to detect presence of any configured canary tokens."""
        text = self._extract_text(item)
        findings: list[SecurityFinding] = []

        for canary in self._canaries:
            matched = False
            if canary.case_sensitive:
                matched = canary.canary_value in text
            else:
                matched = canary.canary_value.lower() in text.lower()

            if matched:
                findings.append(
                    SecurityFinding(
                        category=self.finding_category,
                        severity=Severity.CRITICAL,
                        source=self.detector_id,
                        explanation=(
                            f"Configured synthetic canary token '{canary.canary_id}' "
                            "was detected in the scanned payload."
                        ),
                        metadata={
                            "canary_id": canary.canary_id,
                            "safe_fingerprint": canary.safe_fingerprint,
                        },
                    )
                )

        return tuple(findings)
