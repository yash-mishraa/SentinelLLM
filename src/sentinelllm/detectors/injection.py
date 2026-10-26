"""Deterministic heuristic detector for recognizable prompt-injection patterns."""

import re
from dataclasses import dataclass
from typing import Final

from sentinelllm.contracts.decision import SecurityFinding, Severity
from sentinelllm.contracts.messages import SecurityContent
from sentinelllm.detectors.base import BaseDetector


@dataclass(frozen=True, slots=True)
class InjectionRule:
    """Specification of an injection pattern heuristic rule."""

    rule_id: str
    pattern: re.Pattern[str]
    severity: Severity
    explanation: str


_INJECTION_RULES: Final[tuple[InjectionRule, ...]] = (
    InjectionRule(
        rule_id="INJ_001_INSTRUCTION_OVERRIDE",
        pattern=re.compile(
            r"\b(?:ignore|disregard|forget|clear|override)\s+(?:all\s+)?(?:previous|prior|earlier|above)\s+"
            r"(?:instructions|directives|prompts|rules|commands)\b|"
            r"\b(?:do\s+not|don't)\s+follow\s+(?:any\s+)?(?:previous|prior|earlier|system)\s+"
            r"(?:instructions|directives|prompts|rules)\b",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        explanation="Attempted to explicitly override or clear preceding instructions.",
    ),
    InjectionRule(
        rule_id="INJ_002_ROLE_JAILBREAK",
        pattern=re.compile(
            r"\b(?:you\s+are\s+now|enter|switch\s+to|enable)\s+(?:in\s+)?(?:developer\s+mode|dan\s+mode|"
            r"jailbreak(?:\s+mode)?|god\s+mode|unrestricted\s+mode|unfiltered\s+mode)\b|"
            r"\bact\s+as\s+an?\s+(?:unrestricted|unfiltered|jailbroken|evil)\s+(?:ai|assistant|model|bot)\b",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        explanation="Attempted role-based jailbreak or persona override to bypass safety filters.",
    ),
    InjectionRule(
        rule_id="INJ_003_SYSTEM_OVERRIDE_DELIMITER",
        pattern=re.compile(
            r"(?:^|\n)\s*(?:\[|\{|\(|###|\*\*)?\s*(?:system|admin|root|developer)\s+override\s*(?:\]|\}|\)|:|\n|###|\*\*)|"
            r"(?:^|\n)\s*(?:\[|\{)?\s*new\s+system\s+instructions\s*(?:begin\s+here|start\s+now|\]|\}|:)",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        explanation="Attempted delimiter injection or fake instruction header insertion.",
    ),
    InjectionRule(
        rule_id="INJ_004_PREVIOUS_CONTEXT_DUMP",
        pattern=re.compile(
            r"\b(?:output|print|repeat|display|dump|echo)\s+(?:all\s+)?(?:the\s+)?"
            r"(?:text|content|instructions|prompts?)\s+(?:above|prior\s+to\s+this|preceding\s+this)\b|"
            r"\b(?:repeat|print|output)\s+everything\s+(?:above|prior\s+to\s+this)\b",
            re.IGNORECASE,
        ),
        severity=Severity.MEDIUM,
        explanation="Attempted to dump or repeat preceding context or prompt preamble.",
    ),
)


class InjectionPatternDetector(BaseDetector):
    """Detects explicit prompt-injection signatures and role-override indicators."""

    def __init__(
        self,
        rules: tuple[InjectionRule, ...] = _INJECTION_RULES,
        detector_id: str = "heuristic_injection_detector",
    ) -> None:
        self._rules = rules
        self._detector_id = detector_id

    @property
    def detector_id(self) -> str:
        return self._detector_id

    @property
    def finding_category(self) -> str:
        return "prompt_injection"

    def scan(self, item: SecurityContent | str) -> tuple[SecurityFinding, ...]:
        """Scan input content against configured injection rules."""
        text = self._extract_text(item)
        findings: list[SecurityFinding] = []

        for rule in self._rules:
            match = rule.pattern.search(text)
            if match:
                # Deduplicate: one finding per matched rule
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
