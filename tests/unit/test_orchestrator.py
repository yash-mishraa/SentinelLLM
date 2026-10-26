"""Unit tests for the minimal request lifecycle orchestrator."""

from datetime import UTC

import pytest

from sentinelllm.contracts import (
    ApplicationInstruction,
    ContentProvenance,
    RequestContext,
    RetrievedChunk,
    ToolOutput,
    TrustClassification,
    UserMessage,
)
from sentinelllm.orchestrator import LifecycleOrchestrator


class TestLifecycleOrchestrator:
    """Test suite verifying lifecycle orchestration, provenance preservation, and audit logging."""

    def test_orchestrator_preserves_request_id_and_provenance(self) -> None:
        inst = ApplicationInstruction(content="System instruction.")
        user = UserMessage(content="User query.")
        doc = RetrievedChunk(content="Untrusted document.", chunk_id="doc-1")
        tool = ToolOutput(content="Tool result.", tool_name="calculator")

        context = RequestContext(
            request_id="custom-req-001",
            correlation_id="corr-xyz",
            items=(inst, user, doc, tool),
        )

        orchestrator = LifecycleOrchestrator()
        result = orchestrator.process(context)

        # Invariant: request_id and correlation_id preserved
        assert result.request_context.request_id == "custom-req-001"
        assert result.request_context.correlation_id == "corr-xyz"

        # Invariant: items and provenances unchanged
        assert len(result.request_context.items) == 4
        assert (
            result.request_context.items[0].provenance == ContentProvenance.APPLICATION_INSTRUCTION
        )
        assert (
            result.request_context.items[0].trust_classification
            == TrustClassification.TRUSTED_INSTRUCTIONS
        )
        assert result.request_context.items[1].provenance == ContentProvenance.USER_MESSAGE
        assert (
            result.request_context.items[1].trust_classification == TrustClassification.USER_INPUT
        )
        assert result.request_context.items[2].provenance == ContentProvenance.RETRIEVED_DOCUMENT
        assert (
            result.request_context.items[2].trust_classification
            == TrustClassification.UNTRUSTED_CONTEXT
        )
        assert result.request_context.items[3].provenance == ContentProvenance.EXTERNAL_TOOL
        assert (
            result.request_context.items[3].trust_classification
            == TrustClassification.UNTRUSTED_CONTEXT
        )

        # Invariant: provenance summary counts
        assert result.provenance_summary == {
            "application_instruction": 1,
            "external_tool": 1,
            "retrieved_document": 1,
            "user_message": 1,
        }
        assert result.item_count == 4
        assert result.status == "accepted"

    def test_audit_events_emitted_with_utc_timestamps_and_sanitized_data(self) -> None:
        raw_user_prompt = "Super sensitive financial information that must not leak into logs."
        context = RequestContext(
            request_id="req-audit-test",
            items=(UserMessage(content=raw_user_prompt),),
        )

        orchestrator = LifecycleOrchestrator(component_name="test_orchestrator")
        result = orchestrator.process(context)

        assert len(result.audit_events) == 2
        received_event, processed_event = result.audit_events

        # Timestamps are valid UTC
        for event in (received_event, processed_event):
            assert event.request_id == "req-audit-test"
            assert event.component == "test_orchestrator"
            assert event.timestamp.tzinfo == UTC

        # Invariant: Raw prompt text is NOT included in audit events
        for event in result.audit_events:
            for val in event.metadata.values():
                assert raw_user_prompt not in str(val)

        assert received_event.event_type == "lifecycle.request_received"
        assert received_event.metadata["item_count"] == 1
        assert received_event.metadata["provenance_summary"] == {"user_message": 1}

        assert processed_event.event_type == "lifecycle.context_processed"
        assert processed_event.metadata["status"] == "accepted"

    def test_deterministic_orchestrator_behavior(self) -> None:
        """The orchestrator must produce deterministic summaries for identical context."""
        context = RequestContext(
            request_id="det-req-1",
            items=(
                ApplicationInstruction(content="Rule 1"),
                UserMessage(content="Question"),
            ),
        )
        orchestrator = LifecycleOrchestrator()

        res1 = orchestrator.process(context)
        res2 = orchestrator.process(context)

        assert res1.item_count == res2.item_count
        assert res1.provenance_summary == res2.provenance_summary
        assert res1.status == res2.status
        assert res1.request_context.request_id == res2.request_context.request_id

    def test_orchestrator_rejects_invalid_context_type(self) -> None:
        orchestrator = LifecycleOrchestrator()
        with pytest.raises(TypeError, match="Expected RequestContext instance"):
            orchestrator.process(
                {"request_id": "fake"}  # type: ignore[arg-type]
            )
