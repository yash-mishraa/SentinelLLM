"""Typed message and context models with explicit provenance and trust binding."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sentinelllm.contracts.provenance import (
    ContentProvenance,
    TrustClassification,
    assert_valid_trust_binding,
)


class BaseContentItem(BaseModel):
    """Base class for all content items participating in the security pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    content: str
    provenance: ContentProvenance
    trust_classification: TrustClassification
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_trust_invariants(self) -> "BaseContentItem":
        assert_valid_trust_binding(self.provenance, self.trust_classification)
        return self


class ApplicationInstruction(BaseContentItem):
    """Application-controlled developer or system instructions.

    These instructions originate exclusively from the host application codebase
    and carry instruction authority (`TRUSTED_INSTRUCTIONS`).
    """

    content: Annotated[str, Field(min_length=1)]
    provenance: Literal[ContentProvenance.APPLICATION_INSTRUCTION] = (
        ContentProvenance.APPLICATION_INSTRUCTION
    )
    trust_classification: Literal[TrustClassification.TRUSTED_INSTRUCTIONS] = (
        TrustClassification.TRUSTED_INSTRUCTIONS
    )


class UserMessage(BaseContentItem):
    """Direct user prompt submitted during a session.

    Always classified as `USER_INPUT` to prevent prompt text from acquiring
    system instruction authority.
    """

    content: Annotated[str, Field(min_length=1)]
    provenance: Literal[ContentProvenance.USER_MESSAGE] = ContentProvenance.USER_MESSAGE
    trust_classification: Literal[TrustClassification.USER_INPUT] = TrustClassification.USER_INPUT


class RetrievedChunk(BaseContentItem):
    """Retrieved document or knowledge base fragment (e.g., from RAG corpora).

    Always classified as `UNTRUSTED_CONTEXT` to prevent indirect prompt
    injections within third-party documents from being executed as instructions.
    """

    content: Annotated[str, Field(min_length=1)]
    chunk_id: Annotated[str, Field(min_length=1)]
    source: str | None = None
    provenance: Literal[ContentProvenance.RETRIEVED_DOCUMENT] = ContentProvenance.RETRIEVED_DOCUMENT
    trust_classification: Literal[TrustClassification.UNTRUSTED_CONTEXT] = (
        TrustClassification.UNTRUSTED_CONTEXT
    )


class ToolOutput(BaseContentItem):
    """Raw output returned by an executed tool or external API.

    Always classified as `UNTRUSTED_CONTEXT` to protect against secondary
    injections returned from compromised or external web endpoints.
    """

    content: str
    tool_name: Annotated[str, Field(min_length=1)]
    tool_call_id: str | None = None
    provenance: Literal[ContentProvenance.EXTERNAL_TOOL] = ContentProvenance.EXTERNAL_TOOL
    trust_classification: Literal[TrustClassification.UNTRUSTED_CONTEXT] = (
        TrustClassification.UNTRUSTED_CONTEXT
    )


SecurityContent = ApplicationInstruction | UserMessage | RetrievedChunk | ToolOutput
InboundUntrustedContent = UserMessage | RetrievedChunk | ToolOutput


def parse_untrusted_content(payload: dict[str, Any] | str) -> InboundUntrustedContent:
    """Safely parse untrusted external content, preventing instruction escalation.

    Security Invariant:
    Untrusted external inputs can NEVER construct an ApplicationInstruction or
    claim TRUSTED_INSTRUCTIONS authority. Any payload attempting to supply
    application_instruction provenance or trusted_instructions classification
    is strictly rejected.

    Raises:
        ValueError: If payload attempts to spoof application instructions or trusted authority.
        TypeError: If payload is not a dict or string.
    """
    if isinstance(payload, str):
        return UserMessage(content=payload)

    if not isinstance(payload, dict):
        raise TypeError(f"Expected dict or str for untrusted content, got {type(payload).__name__}")

    prov = payload.get("provenance")
    prov_str = (
        str(prov.value if hasattr(prov, "value") else prov).lower() if prov is not None else ""
    )
    if prov_str == ContentProvenance.APPLICATION_INSTRUCTION.value:
        raise ValueError(
            "Security violation: Untrusted serialized input cannot claim "
            "ApplicationInstruction provenance."
        )

    trust = payload.get("trust_classification")
    trust_str = (
        str(trust.value if hasattr(trust, "value") else trust).lower() if trust is not None else ""
    )
    if trust_str == TrustClassification.TRUSTED_INSTRUCTIONS.value:
        raise ValueError(
            "Security violation: Untrusted serialized input cannot claim "
            "TRUSTED_INSTRUCTIONS authority."
        )

    # Resolve to appropriate untrusted message model
    if prov in (ContentProvenance.RETRIEVED_DOCUMENT, ContentProvenance.RETRIEVED_DOCUMENT.value):
        return RetrievedChunk.model_validate(payload)
    if prov in (ContentProvenance.EXTERNAL_TOOL, ContentProvenance.EXTERNAL_TOOL.value):
        return ToolOutput.model_validate(payload)

    return UserMessage.model_validate(payload)
