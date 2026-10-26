"""SentinelLLM: Runtime security controls and defense-in-depth for LLM applications.

This package provides policy enforcement, trust boundary isolation, output
validation, and safe tool execution primitives for language model workloads.
"""

from typing import Final

from sentinelllm.approvals import (
    ApprovalRequest,
    ApprovalService,
    ApprovalStatus,
    InMemoryApprovalStore,
    compute_argument_hash,
)
from sentinelllm.contracts import (
    ApplicationInstruction,
    AuditEvent,
    BaseContentItem,
    ContentProvenance,
    Decision,
    InboundUntrustedContent,
    RequestContext,
    RetrievedChunk,
    SecurityContent,
    SecurityDecision,
    SecurityFinding,
    Severity,
    ToolOutput,
    TrustClassification,
    assert_valid_trust_binding,
    parse_untrusted_content,
    parse_untrusted_context,
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
from sentinelllm.policy import (
    AnonymousPrincipal,
    AuthenticatedPrincipal,
    AuthorizationRequest,
    PolicyConfig,
    PolicyDecisionPoint,
    PolicyRule,
)
from sentinelllm.tools import (
    PolicyEnforcementPoint,
    ToolExecutionResult,
    ToolRegistry,
    ToolSpec,
)

__version__: Final[str] = "0.1.0.dev0"

__all__: Final[list[str]] = [
    "AnonymousPrincipal",
    "ApplicationInstruction",
    "ApprovalRequest",
    "ApprovalService",
    "ApprovalStatus",
    "AuditEvent",
    "AuthenticatedPrincipal",
    "AuthorizationRequest",
    "BaseContentItem",
    "BaseDetector",
    "CanaryConfig",
    "CanaryLeakDetector",
    "ContentProvenance",
    "Decision",
    "DetectorRegistry",
    "ExtractionRule",
    "InMemoryApprovalStore",
    "InboundUntrustedContent",
    "InjectionPatternDetector",
    "InjectionRule",
    "InstructionExtractionDetector",
    "LifecycleOrchestrator",
    "LifecycleResult",
    "PolicyConfig",
    "PolicyDecisionPoint",
    "PolicyEnforcementPoint",
    "PolicyRule",
    "RequestContext",
    "RetrievedChunk",
    "SecurityContent",
    "SecurityDecision",
    "SecurityFinding",
    "Severity",
    "ToolExecutionResult",
    "ToolOutput",
    "ToolRegistry",
    "ToolSpec",
    "TrustClassification",
    "__version__",
    "assert_valid_trust_binding",
    "compute_argument_hash",
    "parse_untrusted_content",
    "parse_untrusted_context",
]
