"""Public contract models and types for SentinelLLM."""

from sentinelllm.contracts.audit import AuditEvent
from sentinelllm.contracts.context import RequestContext, parse_untrusted_context
from sentinelllm.contracts.decision import (
    Decision,
    SecurityDecision,
    SecurityFinding,
    Severity,
)
from sentinelllm.contracts.messages import (
    ApplicationInstruction,
    BaseContentItem,
    InboundUntrustedContent,
    RetrievedChunk,
    SecurityContent,
    ToolOutput,
    UserMessage,
    parse_untrusted_content,
)
from sentinelllm.contracts.provenance import (
    ContentProvenance,
    TrustClassification,
    assert_valid_trust_binding,
)

__all__ = [
    "ApplicationInstruction",
    "AuditEvent",
    "BaseContentItem",
    "ContentProvenance",
    "Decision",
    "InboundUntrustedContent",
    "RequestContext",
    "RetrievedChunk",
    "SecurityContent",
    "SecurityDecision",
    "SecurityFinding",
    "Severity",
    "ToolOutput",
    "TrustClassification",
    "UserMessage",
    "assert_valid_trust_binding",
    "parse_untrusted_content",
    "parse_untrusted_context",
]
