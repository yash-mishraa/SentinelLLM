"""Unit and integration tests for the Policy Enforcement Point (PEP) and simulated tools."""

import json

import pytest

from sentinelllm.contracts import Decision, SecurityFinding, Severity
from sentinelllm.policy import (
    REASON_ALLOW_EXPLICIT,
    REASON_DENY_HIGH_RISK_FINDINGS,
    REASON_DENY_INSUFFICIENT_PERMISSION,
    REASON_DENY_INVALID_ARGUMENTS,
    REASON_DENY_MISSING_IDENTITY,
    REASON_DENY_UNKNOWN_TOOL,
    REASON_REVIEW_APPROVAL_REQUIRED,
    AuthenticatedPrincipal,
    PolicyConfig,
    PolicyDecisionPoint,
    PolicyRule,
)
from sentinelllm.tools import (
    PolicyEnforcementPoint,
    SearchDocumentsArgs,
    ToolRegistry,
    ToolSpec,
)


class TestPolicyEnforcementPoint:
    """Test suite verifying PEP action gating, argument schema validation, and audit logging."""

    def test_authorized_user_executes_permitted_search(self) -> None:
        pep = PolicyEnforcementPoint()
        principal = AuthenticatedPrincipal(
            principal_id="search_user",
            permissions=frozenset({"documents:search"}),
        )

        result = pep.invoke(
            tool_name="search_documents",
            raw_arguments={"query": "retention", "limit": 2},
            principal=principal,
            request_id="req-search-01",
        )

        assert result.status == "executed"
        assert result.reason_code == REASON_ALLOW_EXPLICIT
        assert result.decision is not None and result.decision.decision == Decision.ALLOW
        assert result.output is not None
        assert result.output.tool_name == "search_documents"

        # Content is valid JSON with expected matches
        parsed = json.loads(result.output.content)
        assert len(parsed) >= 1
        assert parsed[0]["doc_id"] == "doc_001"

        # Verifies audit event was emitted
        assert len(result.audit_events) == 1
        event = result.audit_events[0]
        assert event.event_type == "tool.executed"
        assert event.decision == Decision.ALLOW
        assert event.metadata["tool_name"] == "search_documents"
        assert event.metadata["principal_id"] == "search_user"

    def test_authorized_user_reads_customer_record(self) -> None:
        pep = PolicyEnforcementPoint()
        principal = AuthenticatedPrincipal(
            principal_id="support_agent",
            permissions=frozenset({"records:read"}),
        )

        result = pep.invoke(
            tool_name="read_customer_record",
            raw_arguments={"customer_id": "cust_001"},
            principal=principal,
        )

        assert result.status == "executed"
        assert result.output is not None
        record = json.loads(result.output.content)
        assert record["name"] == "Jane Doe"
        assert record["tier"] == "enterprise"

    def test_unauthorized_user_cannot_read_customer_record(self) -> None:
        pep = PolicyEnforcementPoint()
        # User lacks 'records:read'
        unauthorized = AuthenticatedPrincipal(
            principal_id="unauthorized_guest",
            permissions=frozenset({"documents:search"}),
        )

        result = pep.invoke(
            tool_name="read_customer_record",
            raw_arguments={"customer_id": "cust_001"},
            principal=unauthorized,
        )

        assert result.status == "denied"
        assert result.reason_code == REASON_DENY_INSUFFICIENT_PERMISSION
        assert result.output is None
        assert result.decision is not None and result.decision.decision == Decision.BLOCK

        # Emitted audit event captures rejection
        assert len(result.audit_events) == 1
        assert result.audit_events[0].event_type == "tool.rejected"
        assert result.audit_events[0].metadata["reason_code"] == REASON_DENY_INSUFFICIENT_PERMISSION

    def test_sensitive_export_requires_approval_and_remains_unexecuted(self) -> None:
        pep = PolicyEnforcementPoint()
        # Principal has export permission, but policy mandates review/approval
        analyst = AuthenticatedPrincipal(
            principal_id="data_analyst",
            permissions=frozenset({"records:export"}),
        )

        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "archive"},
            principal=analyst,
        )

        # Fails closed into pending_approval status without executing tool
        assert result.status == "pending_approval"
        assert result.reason_code == REASON_REVIEW_APPROVAL_REQUIRED
        assert result.output is None
        assert result.decision is not None and result.decision.decision == Decision.REVIEW

        # Audit event records review_required
        assert len(result.audit_events) == 1
        assert result.audit_events[0].event_type == "tool.review_required"

    def test_unknown_tool_fails_closed(self) -> None:
        pep = PolicyEnforcementPoint()
        admin = AuthenticatedPrincipal(
            principal_id="admin_user",
            roles=frozenset({"admin"}),
            permissions=frozenset({"*"}),
        )

        result = pep.invoke(
            tool_name="unknown_arbitrary_shell_command",
            raw_arguments={"cmd": "rm -rf /"},
            principal=admin,
        )

        assert result.status == "denied"
        assert result.reason_code == REASON_DENY_UNKNOWN_TOOL
        assert result.output is None
        assert "not registered" in str(result.error_message)

    def test_invalid_arguments_rejected_before_tool_execution(self) -> None:
        pep = PolicyEnforcementPoint()
        admin = AuthenticatedPrincipal(
            principal_id="admin_user",
            roles=frozenset({"admin"}),
            permissions=frozenset({"*"}),
        )

        # Missing required 'customer_id' argument
        result = pep.invoke(
            tool_name="read_customer_record",
            raw_arguments={},
            principal=admin,
        )

        assert result.status == "denied"
        assert result.reason_code == REASON_DENY_INVALID_ARGUMENTS
        assert result.output is None
        assert "Invalid arguments" in str(result.error_message)

    def test_missing_principal_identity_fails_closed(self) -> None:
        pep = PolicyEnforcementPoint()

        result = pep.invoke(
            tool_name="search_documents",
            raw_arguments={"query": "security"},
            principal=None,
        )

        assert result.status == "denied"
        assert result.reason_code == REASON_DENY_MISSING_IDENTITY
        assert result.output is None

    def test_high_risk_finding_blocks_tool_invocation(self) -> None:
        pep = PolicyEnforcementPoint()
        authorized = AuthenticatedPrincipal(
            principal_id="user_doc_reader",
            permissions=frozenset({"documents:search"}),
        )

        injection_finding = SecurityFinding(
            category="prompt_injection",
            severity=Severity.HIGH,
            source="heuristic_injection_detector",
            explanation="Instruction override pattern detected",
        )

        result = pep.invoke(
            tool_name="search_documents",
            raw_arguments={"query": "test"},
            principal=authorized,
            findings=(injection_finding,),
        )

        assert result.status == "denied"
        assert result.reason_code == REASON_DENY_HIGH_RISK_FINDINGS
        assert result.output is None

    def test_tool_exception_does_not_turn_into_success(self) -> None:
        """Exceptions in tool handlers must fail closed and record error telemetry."""
        registry = ToolRegistry()
        failing_spec = ToolSpec(
            tool_name="failing_tool",
            description="Tool that raises an unexpected exception",
            action_identifier="tools:execute:failing_tool",
            resource_classification="documents",
            argument_schema=SearchDocumentsArgs,
        )

        def buggy_handler(args: SearchDocumentsArgs) -> str:
            raise RuntimeError("Underlying database connection dropped")

        registry.register(failing_spec, buggy_handler)

        pdp = PolicyDecisionPoint(
            config=PolicyConfig(
                rules=(
                    PolicyRule(
                        rule_id="RULE_ALLOW_FAILING",
                        action_pattern="tools:execute:failing_tool",
                        resource_pattern="documents",
                        effect=Decision.ALLOW,
                        reason_code=REASON_ALLOW_EXPLICIT,
                    ),
                )
            )
        )
        pep = PolicyEnforcementPoint(pdp=pdp, registry=registry)
        user = AuthenticatedPrincipal(principal_id="test_user")

        result = pep.invoke(
            tool_name="failing_tool",
            raw_arguments={"query": "test"},
            principal=user,
        )

        assert result.status == "error"
        assert result.reason_code == "EXECUTION_ERROR"
        assert "Underlying database connection dropped" in str(result.error_message)
        assert result.output is None
        assert len(result.audit_events) == 1
        assert result.audit_events[0].event_type == "tool.error"

    def test_simulated_tools_edge_cases_and_handlers(self) -> None:
        from pydantic import BaseModel

        from sentinelllm.tools.simulated import (
            ExportCustomerRecordsArgs,
            execute_export_customer_records,
            execute_read_customer_record,
            execute_search_documents,
        )

        # Customer not found
        pep = PolicyEnforcementPoint()
        principal = AuthenticatedPrincipal(
            principal_id="support",
            permissions=frozenset({"records:read"}),
        )
        res = pep.invoke(
            tool_name="read_customer_record",
            raw_arguments={"customer_id": "cust_999"},
            principal=principal,
        )
        assert res.status == "executed"
        assert res.output is not None
        assert "not found" in res.output.content

        # Direct execution of export handler
        export_out = execute_export_customer_records(ExportCustomerRecordsArgs())
        assert "exported" in export_out

        # Direct handlers type error checks
        class DummyArgs(BaseModel):
            pass

        with pytest.raises(TypeError, match="Expected SearchDocumentsArgs"):
            execute_search_documents(DummyArgs())

        with pytest.raises(TypeError, match="Expected ReadCustomerRecordArgs"):
            execute_read_customer_record(DummyArgs())

        with pytest.raises(TypeError, match="Expected ExportCustomerRecordsArgs"):
            execute_export_customer_records(DummyArgs())

    def test_tool_registry_validation(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(TypeError, match="Expected ToolSpec"):
            registry.register("not_a_spec", lambda x: "out")  # type: ignore[arg-type]

        from sentinelllm.tools import SPEC_SEARCH_DOCUMENTS

        with pytest.raises(TypeError, match="must be callable"):
            registry.register(SPEC_SEARCH_DOCUMENTS, "not_callable")  # type: ignore[arg-type]

        with pytest.raises(KeyError, match="No execution handler registered"):
            registry.execute("unregistered", SearchDocumentsArgs(query="test"))
