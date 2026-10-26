"""Detection subsystem for heuristic and pattern-based security analysis."""

from sentinelllm.detectors.base import BaseDetector
from sentinelllm.detectors.canary import CanaryConfig, CanaryLeakDetector
from sentinelllm.detectors.extraction import (
    ExtractionRule,
    InstructionExtractionDetector,
)
from sentinelllm.detectors.injection import (
    InjectionPatternDetector,
    InjectionRule,
)
from sentinelllm.detectors.registry import DetectorRegistry

__all__ = [
    "BaseDetector",
    "CanaryConfig",
    "CanaryLeakDetector",
    "DetectorRegistry",
    "ExtractionRule",
    "InjectionPatternDetector",
    "InjectionRule",
    "InstructionExtractionDetector",
]
