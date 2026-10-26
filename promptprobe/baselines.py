"""Evaluation baseline configurations for comparative benchmarking."""

from typing import Final

from sentinelllm.detectors.canary import CanaryConfig, CanaryLeakDetector
from sentinelllm.detectors.extraction import InstructionExtractionDetector
from sentinelllm.detectors.injection import InjectionPatternDetector
from sentinelllm.detectors.registry import DetectorRegistry
from sentinelllm.policy.engine import PolicyDecisionPoint
from sentinelllm.tools.pep import PolicyEnforcementPoint

BASELINE_NO_DETECTION: Final[str] = "no_detection_baseline"
BASELINE_HEURISTIC: Final[str] = "heuristic_defense"

# Benchmark synthetic canary token
BENCHMARK_CANARIES: Final[list[CanaryConfig]] = [
    CanaryConfig(
        canary_id="canary_synthetic_bench_01",
        canary_value="CANARY_SEC_TOKEN_890123",
    ),
]


def create_heuristic_defense() -> tuple[
    DetectorRegistry, PolicyDecisionPoint, PolicyEnforcementPoint
]:
    """Create the full heuristic defense suite (current SentinelLLM implementation)."""
    registry = DetectorRegistry()
    registry.register(InjectionPatternDetector())
    registry.register(InstructionExtractionDetector())
    registry.register(CanaryLeakDetector(canaries=BENCHMARK_CANARIES))

    pdp = PolicyDecisionPoint()
    pep = PolicyEnforcementPoint(pdp=pdp)
    return registry, pdp, pep


def create_no_detection_baseline() -> tuple[
    DetectorRegistry, PolicyDecisionPoint, PolicyEnforcementPoint
]:
    """Create an unprotected baseline with zero active detectors."""
    # Explicitly empty detector suite with zero registered scanners
    empty_registry = DetectorRegistry(detectors=[])
    pdp = PolicyDecisionPoint()
    pep = PolicyEnforcementPoint(pdp=pdp)
    return empty_registry, pdp, pep
