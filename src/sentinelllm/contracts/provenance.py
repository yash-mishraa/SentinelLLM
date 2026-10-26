"""Content provenance and trust classification contracts.

This module defines the explicit origin of content processed by SentinelLLM
and the distinct, application-governed trust classifications applied to it.
"""

from enum import StrEnum
from typing import Final


class ContentProvenance(StrEnum):
    """The physical source or channel through which content arrived."""

    APPLICATION_INSTRUCTION = "application_instruction"
    USER_MESSAGE = "user_message"
    RETRIEVED_DOCUMENT = "retrieved_document"
    EXTERNAL_TOOL = "external_tool"


class TrustClassification(StrEnum):
    """The authority level granted by application policy to content.

    Security Invariant:
    Untrusted external content (user inputs, retrieved documents, external tool
    outputs) must NEVER receive TRUSTED_INSTRUCTIONS authority, regardless of
    any claims or instructions contained within the payload text itself.
    """

    TRUSTED_INSTRUCTIONS = "trusted_instructions"
    USER_INPUT = "user_input"
    UNTRUSTED_CONTEXT = "untrusted_context"


# Provenances permitted to receive instruction authority
_TRUSTED_PROVENANCE_ALLOWLIST: Final[frozenset[ContentProvenance]] = frozenset(
    {ContentProvenance.APPLICATION_INSTRUCTION}
)


def assert_valid_trust_binding(
    provenance: ContentProvenance,
    trust: TrustClassification,
) -> None:
    """Validate that provenance and trust classification do not violate security invariants.

    Raises:
        ValueError: If untrusted provenance is paired with TRUSTED_INSTRUCTIONS authority.
    """
    if (
        trust == TrustClassification.TRUSTED_INSTRUCTIONS
        and provenance not in _TRUSTED_PROVENANCE_ALLOWLIST
    ):
        raise ValueError(
            f"Security violation: Provenance '{provenance.value}' cannot be classified "
            f"as '{trust.value}'. Only application-controlled instructions may hold "
            "instruction authority."
        )
