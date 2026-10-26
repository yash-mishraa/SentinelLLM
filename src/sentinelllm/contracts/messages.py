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
