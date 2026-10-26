"""SentinelLLM: Runtime security controls and defense-in-depth for LLM applications.

This package provides policy enforcement, trust boundary isolation, output
validation, and safe tool execution primitives for language model workloads.
"""

from typing import Final

from sentinelllm.contracts import (
    ApplicationInstruction,
    AuditEvent,
    BaseContentItem,
    ContentProvenance,
    Decision,
    RequestContext,
    RetrievedChunk,
    SecurityContent,
    SecurityDecision,
    SecurityFinding,
    Severity,
    ToolOutput,
    TrustClassification,
    assert_valid_trust_binding,
)
from sentinelllm.detectors import (
    BaseDetector,
    CanaryConfig,
    CanaryLeakDetector,
    DetectorRegistry,
    ExtractionRule,
    InjectionPatternDetector,
    InjectionRule,
    InstructionExtractionDetector,
)
from sentinelllm.orchestrator import LifecycleOrchestrator, LifecycleResult

__version__: Final[str] = "0.1.0.dev0"

__all__: Final[list[str]] = [
    "ApplicationInstruction",
    "AuditEvent",
    "BaseContentItem",
    "BaseDetector",
    "CanaryConfig",
    "CanaryLeakDetector",
    "ContentProvenance",
    "Decision",
    "DetectorRegistry",
    "ExtractionRule",
    "InjectionPatternDetector",
    "InjectionRule",
    "InstructionExtractionDetector",
    "LifecycleOrchestrator",
    "LifecycleResult",
    "RequestContext",
    "RetrievedChunk",
    "SecurityContent",
    "SecurityDecision",
    "SecurityFinding",
    "Severity",
    "ToolOutput",
    "TrustClassification",
    "__version__",
    "assert_valid_trust_binding",
]
