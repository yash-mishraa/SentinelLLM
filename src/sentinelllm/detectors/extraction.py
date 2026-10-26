"""Deterministic heuristic detector for sensitive instruction extraction attempts."""

import re
from dataclasses import dataclass
from typing import Final

from sentinelllm.contracts.decision import SecurityFinding, Severity
from sentinelllm.contracts.messages import SecurityContent
from sentinelllm.detectors.base import BaseDetector


@dataclass(frozen=True, slots=True)
class ExtractionRule:
    """Specification of an instruction extraction heuristic rule."""

    rule_id: str
    pattern: re.Pattern[str]
    severity: Severity
    explanation: str


_EXTRACTION_RULES: Final[tuple[ExtractionRule, ...]] = (
    ExtractionRule(
        rule_id="EXT_001_SYSTEM_PROMPT_EXTRACTION",
        pattern=re.compile(
            r"\b(?:reveal|show|display|disclose|print|output|provide|give\s+me)\s+"
            r"(?:me\s+)?(?:all\s+)?(?:(?:your|the)\s+)?"
            r"(?:system\s+prompt|developer\s+instructions?|system\s+instructions?|base\s+instructions?)\b|"
            r"\bwhat\s+(?:is|are)\s+(?:all\s+)?(?:your|the)\s+"
            r"(?:system\s+prompt|developer\s+instructions?|system\s+instructions?|base\s+instructions?)\b|"
            r"\b(?:print|show|repeat|output)\s+(?:your\s+)?exact\s+system\s+prompt\b",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        explanation="Attempted to extract application system prompt or developer instructions.",
    ),
    ExtractionRule(
        rule_id="EXT_002_HIDDEN_RULES_EXTRACTION",
        pattern=re.compile(
            r"\b(?:what\s+(?:were|are)\s+you\s+(?:instructed|told|commanded)\s+to\s+(?:do|follow)|"
            r"(?:reveal|show|dump|leak)\s+(?:your\s+)?(?:hidden|secret|confidential)\s+"
            r"(?:rules|directives|instructions|configuration))\b",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        explanation="Attempted to elicit confidential or hidden application directives.",
    ),
    ExtractionRule(
        rule_id="EXT_003_VERBATIM_PREAMBLE_EXTRACTION",
        pattern=re.compile(
            r"\b(?:output|print|recite|display)\s+(?:your\s+)?(?:initial|first)\s+"
            r"(?:prompt|instructions?)\s+verbatim\b|"
            r"\brecite\s+everything\s+(?:you\s+were\s+told|from\s+the\s+beginning)\b",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        explanation="Attempted verbatim extraction of model configuration preamble.",
    ),
)


class InstructionExtractionDetector(BaseDetector):
    """Detects targeted attempts to elicit system prompts and confidential directives.

    Limitations:
    This detector identifies linguistic extraction patterns. It does not determine
    whether a subsequent model completion actually leaks secret information.
    """

    def __init__(
        self,
        rules: tuple[ExtractionRule, ...] = _EXTRACTION_RULES,
        detector_id: str = "heuristic_extraction_detector",
    ) -> None:
        self._rules = rules
        self._detector_id = detector_id

    @property
    def detector_id(self) -> str:
        return self._detector_id

    @property
    def finding_category(self) -> str:
        return "instruction_extraction"

    def scan(self, item: SecurityContent | str) -> tuple[SecurityFinding, ...]:
        """Scan input content against configured instruction extraction rules."""
        text = self._extract_text(item)
        findings: list[SecurityFinding] = []

        for rule in self._rules:
            match = rule.pattern.search(text)
            if match:
                findings.append(
                    SecurityFinding(
                        category=self.finding_category,
                        severity=rule.severity,
                        source=self.detector_id,
                        explanation=rule.explanation,
                        metadata={
                            "rule_id": rule.rule_id,
                            "match_span": list(match.span()),
                        },
                    )
                )

        return tuple(findings)
