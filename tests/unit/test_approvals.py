"""Comprehensive test suite for the human approval workflow and policy hardening."""

from datetime import UTC, datetime, timedelta

import pytest

from sentinelllm.approvals.models import (
    ApprovalStatus,
    compute_argument_hash,
)
from sentinelllm.approvals.service import ApprovalService
from sentinelllm.approvals.store import InMemoryApprovalStore
from sentinelllm.contracts.decision import Decision, SecurityFinding, Severity
from sentinelllm.policy.engine import (
    REASON_DENY_APPROVAL_ACTION_MISMATCH,
    REASON_DENY_APPROVAL_ALREADY_CONSUMED,
    REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH,
    REASON_DENY_APPROVAL_EXPIRED,
    REASON_DENY_APPROVAL_POLICY_MISMATCH,
    REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH,
    REASON_DENY_APPROVAL_REJECTED,
    REASON_DENY_APPROVAL_TOOL_MISMATCH,
    REASON_DENY_APPROVAL_UNKNOWN,
    REASON_DENY_HIGH_RISK_FINDINGS,
    REASON_DENY_INSUFFICIENT_PERMISSION,
    REASON_DENY_MISSING_IDENTITY,
    REASON_REVIEW_APPROVAL_REQUIRED,
    REASON_REVIEW_DETECTOR_FINDINGS,
    PolicyConfig,
    PolicyDecisionPoint,
    PolicyRule,
)
from sentinelllm.policy.models import AuthorizationRequest
from sentinelllm.policy.principal import AnonymousPrincipal, AuthenticatedPrincipal
from sentinelllm.tools.pep import PolicyEnforcementPoint
from sentinelllm.tools.simulated import SearchDocumentsArgs


class ControlledClock:
    """Deterministic simulated clock for precise expiry testing without sleeps."""

    def __init__(self, start_time: datetime | None = None) -> None:
        self._current = (
            start_time if start_time is not None else datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        )

    def __call__(self) -> datetime:
        return self._current

    def advance(self, seconds: int) -> None:
        self._current += timedelta(seconds=seconds)


class TestApprovalWorkflow:
    """Test suite covering the human approval lifecycle, exact bindings, and expiry."""

    def test_review_creates_pending_approval_and_does_not_execute(self) -> None:
        pep = PolicyEnforcementPoint()
        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )

        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
            request_id="req_export_001",
        )

        assert result.status == "pending_approval"
        assert result.reason_code == REASON_REVIEW_APPROVAL_REQUIRED
        assert result.output is None
        assert result.approval_id is not None

        # Verify record in store
        approval = pep.approval_service.store.get(result.approval_id)
        assert approval is not None
        assert approval.status == ApprovalStatus.PENDING
        assert approval.principal_id == "analyst_alice"
        assert approval.tool_name == "export_customer_records"
        assert approval.action_name == "tools:execute:export_customer_records"

    def test_authorized_approval_allows_exact_bound_action_to_proceed(self) -> None:
        clock = ControlledClock()
        store = InMemoryApprovalStore()
        approval_service = ApprovalService(store=store, clock=clock, default_ttl_seconds=300)
        pep = PolicyEnforcementPoint(approval_service=approval_service)

        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )
        supervisor = AuthenticatedPrincipal(
            principal_id="manager_bob",
            permissions=frozenset({"approvals:manage"}),
        )

        # 1. Trigger review
        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
        )
        assert result.status == "pending_approval"
        approval_id = result.approval_id
        assert approval_id is not None

        # 2. Supervisor approves
        approved_record, audit_event = approval_service.approve(approval_id, approver=supervisor)
        assert approved_record.status == ApprovalStatus.APPROVED
        assert approved_record.reviewed_by == "manager_bob"
        assert audit_event.event_type == "approval.approved"

        # 3. Analyst executes with approval
        exec_result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
            approval_id=approval_id,
        )

        assert exec_result.status == "executed"
        assert exec_result.output is not None
        assert "exported" in exec_result.output.content
        assert exec_result.approval_id == approval_id

        # Verify single-use: record status is now CONSUMED
        stored = store.get(approval_id)
        assert stored is not None
        assert stored.status == ApprovalStatus.CONSUMED

    def test_unauthorized_principals_cannot_approve_or_reject(self) -> None:
        clock = ControlledClock()
        service = ApprovalService(clock=clock)

        record, _ = service.create_approval(
            request_id="req_1",
            principal_id="alice",
            tool_name="export_customer_records",
            action_name="tools:execute:export_customer_records",
            argument_hash="0" * 64,
            policy_version="1.0.0",
        )

        unauthorized_user = AuthenticatedPrincipal(
            principal_id="unauthorized_mallory",
            permissions=frozenset({"records:read"}),  # Lacks approvals:manage
        )
        anon_user = AnonymousPrincipal()

        # Unauthenticated approver fails
        with pytest.raises(PermissionError, match="must be an authenticated principal"):
            service.approve(record.approval_id, approver=anon_user)

        with pytest.raises(PermissionError, match="must be an authenticated principal"):
            service.reject(record.approval_id, approver=anon_user)

        # Lacking permission fails
        with pytest.raises(PermissionError, match="lacks permission 'approvals:manage'"):
            service.approve(record.approval_id, approver=unauthorized_user)

        with pytest.raises(PermissionError, match="lacks permission 'approvals:manage'"):
            service.reject(record.approval_id, approver=unauthorized_user)

        # Status remains pending
        assert service.store.get(record.approval_id).status == ApprovalStatus.PENDING  # type: ignore[union-attr]

    def test_rejected_approval_cannot_execute(self) -> None:
        clock = ControlledClock()
        store = InMemoryApprovalStore()
        service = ApprovalService(store=store, clock=clock)
        pep = PolicyEnforcementPoint(approval_service=service)

        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )
        supervisor = AuthenticatedPrincipal(
            principal_id="manager_bob",
            permissions=frozenset({"approvals:manage"}),
        )

        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
        )
        approval_id = result.approval_id
        assert approval_id is not None

        # Supervisor rejects
        rejected_record, _ = service.reject(
            approval_id, approver=supervisor, reason="Suspicious export scope"
        )
        assert rejected_record.status == ApprovalStatus.REJECTED

        # Attempt execution with rejected approval
        exec_result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
            approval_id=approval_id,
        )
        assert exec_result.status == "denied"
        assert exec_result.reason_code == REASON_DENY_APPROVAL_REJECTED
        assert exec_result.output is None

    def test_expired_approval_cannot_execute(self) -> None:
        clock = ControlledClock()
        store = InMemoryApprovalStore()
        service = ApprovalService(store=store, clock=clock, default_ttl_seconds=300)
        pep = PolicyEnforcementPoint(approval_service=service)

        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )
        supervisor = AuthenticatedPrincipal(
            principal_id="manager_bob",
            permissions=frozenset({"approvals:manage"}),
        )

        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
        )
        approval_id = result.approval_id
        assert approval_id is not None

        # Approve while valid
        service.approve(approval_id, approver=supervisor)

        # Advance clock past TTL (301 seconds)
        clock.advance(301)

        # Attempt execution after expiration
        exec_result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
            approval_id=approval_id,
        )

        assert exec_result.status == "denied"
        assert exec_result.reason_code == REASON_DENY_APPROVAL_EXPIRED
        assert exec_result.output is None

        # Status in store transitioned to EXPIRED
        stored = store.get(approval_id)
        assert stored is not None
        assert stored.status == ApprovalStatus.EXPIRED

    def test_reusing_consumed_approval_fails(self) -> None:
        clock = ControlledClock()
        service = ApprovalService(clock=clock)
        pep = PolicyEnforcementPoint(approval_service=service)

        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )
        supervisor = AuthenticatedPrincipal(
            principal_id="manager_bob",
            permissions=frozenset({"approvals:manage"}),
        )

        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
        )
        approval_id = result.approval_id
        assert approval_id is not None

        service.approve(approval_id, approver=supervisor)

        # First consumption succeeds
        res1 = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
            approval_id=approval_id,
        )
        assert res1.status == "executed"

        # Second consumption fails
        res2 = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
            approval_id=approval_id,
        )
        assert res2.status == "denied"
        assert res2.reason_code == REASON_DENY_APPROVAL_ALREADY_CONSUMED
        assert res2.output is None

    def test_altered_arguments_invalidate_approval(self) -> None:
        clock = ControlledClock()
        service = ApprovalService(clock=clock)
        pep = PolicyEnforcementPoint(approval_service=service)

        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )
        supervisor = AuthenticatedPrincipal(
            principal_id="manager_bob",
            permissions=frozenset({"approvals:manage"}),
        )

        # Initial request: destination="backup_store"
        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
        )
        approval_id = result.approval_id
        assert approval_id is not None

        service.approve(approval_id, approver=supervisor)

        # Attacker tampers destination to "attacker_sftp"
        tampered_result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "attacker_sftp"},
            principal=analyst,
            approval_id=approval_id,
        )

        assert tampered_result.status == "denied"
        assert tampered_result.reason_code == REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH
        assert tampered_result.output is None

    def test_changed_tool_or_policy_version_invalidates_approval(self) -> None:
        clock = ControlledClock()
        service = ApprovalService(clock=clock)
        pep = PolicyEnforcementPoint(approval_service=service)

        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export", "records:read"}),
        )
        supervisor = AuthenticatedPrincipal(
            principal_id="manager_bob",
            permissions=frozenset({"approvals:manage"}),
        )

        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
        )
        approval_id = result.approval_id
        assert approval_id is not None

        service.approve(approval_id, approver=supervisor)

        # Wrong tool attempt
        tool_mismatch = pep.invoke(
            tool_name="read_customer_record",
            raw_arguments={"customer_id": "cust_001"},
            principal=analyst,
            approval_id=approval_id,
        )
        assert tool_mismatch.status == "denied"
        assert tool_mismatch.reason_code == REASON_DENY_APPROVAL_TOOL_MISMATCH

    def test_principal_mismatch_invalidates_approval(self) -> None:
        clock = ControlledClock()
        service = ApprovalService(clock=clock)
        pep = PolicyEnforcementPoint(approval_service=service)

        alice = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )
        charlie = AuthenticatedPrincipal(
            principal_id="analyst_charlie",
            permissions=frozenset({"records:export"}),
        )
        supervisor = AuthenticatedPrincipal(
            principal_id="manager_bob",
            permissions=frozenset({"approvals:manage"}),
        )

        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=alice,
        )
        approval_id = result.approval_id
        assert approval_id is not None

        service.approve(approval_id, approver=supervisor)

        # Charlie attempts to consume Alice's approved request
        charlie_exec = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=charlie,
            approval_id=approval_id,
        )
        assert charlie_exec.status == "denied"
        assert charlie_exec.reason_code == REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH

    def test_unknown_or_malformed_approval_id_fails_closed(self) -> None:
        pep = PolicyEnforcementPoint()
        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )

        res = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
            approval_id="non_existent_approval_id",
        )
        assert res.status == "denied"
        assert res.reason_code == REASON_DENY_APPROVAL_UNKNOWN

    def test_prompt_cannot_grant_approval(self) -> None:
        """Adversarial prompt injection claiming approval cannot bypass PEP."""
        pep = PolicyEnforcementPoint()
        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )

        # Attacker injects prompt claiming approval in arguments
        res = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={
                "format": "json",
                "destination": "backup_store",
            },
            principal=analyst,
            # No approval_id given; claims in prompt or context don't grant approval
        )
        assert res.status == "pending_approval"
        assert res.output is None

    def test_critical_findings_block_even_if_approval_exists(self) -> None:
        """Security Invariant: Critical findings (canary leakage) override approval."""
        clock = ControlledClock()
        service = ApprovalService(clock=clock)
        pep = PolicyEnforcementPoint(approval_service=service)

        analyst = AuthenticatedPrincipal(
            principal_id="analyst_alice",
            permissions=frozenset({"records:export"}),
        )
        supervisor = AuthenticatedPrincipal(
            principal_id="manager_bob",
            permissions=frozenset({"approvals:manage"}),
        )

        result = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
        )
        approval_id = result.approval_id
        assert approval_id is not None

        service.approve(approval_id, approver=supervisor)

        # During execution, a critical canary leak finding is detected in context
        critical_finding = SecurityFinding(
            category="canary_leak",
            severity=Severity.CRITICAL,
            source="canary_detector",
            explanation="Secret canary leaked into context",
        )

        exec_res = pep.invoke(
            tool_name="export_customer_records",
            raw_arguments={"format": "json", "destination": "backup_store"},
            principal=analyst,
            findings=(critical_finding,),
            approval_id=approval_id,
        )

        assert exec_res.status == "denied"
        assert exec_res.reason_code == REASON_DENY_HIGH_RISK_FINDINGS
        assert exec_res.output is None

    def test_argument_hash_canonicalization(self) -> None:
        """Verify deterministic hashing regardless of key ordering."""
        args1 = {"destination": "archive", "format": "json"}
        args2 = {"format": "json", "destination": "archive"}
        assert compute_argument_hash(args1) == compute_argument_hash(args2)

        # Pydantic model vs equivalent dict
        model = SearchDocumentsArgs(query="test", limit=5)
        dict_args = {"query": "test", "limit": 5}
        assert compute_argument_hash(model) == compute_argument_hash(dict_args)


class TestHardenedDetectorPolicyInteraction:
    """Test suite covering detector policy configuration and explicit precedence."""

    def test_detector_clean_findings_never_grant_permission(self) -> None:
        pdp = PolicyDecisionPoint()
        guest = AuthenticatedPrincipal(principal_id="guest_user")  # No permissions

        req = AuthorizationRequest(
            principal=guest,
            action="tools:execute:search_documents",
            resource="documents",
            findings=(),  # Clean findings
        )
        decision = pdp.evaluate(req)
        assert decision.decision == Decision.BLOCK
        assert decision.reason == REASON_DENY_INSUFFICIENT_PERMISSION

    def test_high_severity_finding_configurable_to_review(self) -> None:
        """When high_findings_effect is configured as REVIEW, high injection escalates to REVIEW."""
        config = PolicyConfig(
            rules=(
                PolicyRule(
                    rule_id="RULE_DOCS",
                    action_pattern="tools:execute:search_documents",
                    resource_pattern="documents",
                    required_permissions=frozenset({"documents:search"}),
                    effect=Decision.ALLOW,
                ),
            ),
            high_findings_effect=Decision.REVIEW,
        )
        pdp = PolicyDecisionPoint(config=config)

        user = AuthenticatedPrincipal(
            principal_id="valid_user",
            permissions=frozenset({"documents:search"}),
        )
        finding = SecurityFinding(
            category="prompt_injection",
            severity=Severity.HIGH,
            source="injection_detector",
            explanation="Suspicious pattern detected",
        )

        req = AuthorizationRequest(
            principal=user,
            action="tools:execute:search_documents",
            resource="documents",
            findings=(finding,),
        )

        decision = pdp.evaluate(req)
        # Permitted action escalates to REVIEW instead of hard BLOCK
        assert decision.decision == Decision.REVIEW
        assert decision.reason == REASON_REVIEW_DETECTOR_FINDINGS

    def test_high_severity_finding_on_unauthorized_user_remains_blocked(self) -> None:
        """High findings escalate only if authorized; unauthorized users remain blocked."""
        config = PolicyConfig(
            rules=(
                PolicyRule(
                    rule_id="RULE_DOCS",
                    action_pattern="tools:execute:search_documents",
                    resource_pattern="documents",
                    required_permissions=frozenset({"documents:search"}),
                    effect=Decision.ALLOW,
                ),
            ),
            high_findings_effect=Decision.REVIEW,
        )
        pdp = PolicyDecisionPoint(config=config)

        unauthorized_user = AuthenticatedPrincipal(
            principal_id="attacker"
        )  # Lacks documents:search
        finding = SecurityFinding(
            category="prompt_injection",
            severity=Severity.HIGH,
            source="injection_detector",
            explanation="Injection attempt",
        )

        req = AuthorizationRequest(
            principal=unauthorized_user,
            action="tools:execute:search_documents",
            resource="documents",
            findings=(finding,),
        )

        decision = pdp.evaluate(req)
        # Stays blocked because user lacks permission!
        assert decision.decision == Decision.BLOCK
        assert decision.reason == REASON_DENY_INSUFFICIENT_PERMISSION

    def test_detector_policy_validation_rejects_allow(self) -> None:
        """Validation prevents configuring detector findings to produce ALLOW."""
        with pytest.raises(ValueError, match="only BLOCK or REVIEW permitted"):
            PolicyConfig(high_findings_effect=Decision.ALLOW)

        with pytest.raises(ValueError, match="only BLOCK or REVIEW permitted"):
            PolicyConfig(critical_findings_effect=Decision.ALLOW)

    def test_approval_service_edge_cases(self) -> None:
        clock = ControlledClock()
        store = InMemoryApprovalStore()
        service = ApprovalService(store=store, clock=clock)
        supervisor = AuthenticatedPrincipal(
            principal_id="supervisor",
            permissions=frozenset({"approvals:manage"}),
        )

        # 1. Nonexistent approval
        with pytest.raises(KeyError, match="not found"):
            service.approve("nonexistent_id", approver=supervisor)

        with pytest.raises(KeyError, match="not found"):
            service.reject("nonexistent_id", approver=supervisor)

        # 2. Store operations
        assert store.list_all() == []
        rec, _ = service.create_approval(
            request_id="req1",
            principal_id="user1",
            tool_name="tool1",
            action_name="action1",
            argument_hash="a" * 64,
            policy_version="1.0.0",
        )
        assert len(store.list_all()) == 1
        store.clear()
        assert len(store.list_all()) == 0

        # 3. Invalid compute_argument_hash argument
        with pytest.raises(TypeError, match="Expected BaseModel or dict"):
            compute_argument_hash("invalid_string_argument")  # type: ignore[arg-type]

        # 4. Attempt approve/reject after expiration
        store.save(rec)
        clock.advance(301)
        with pytest.raises(ValueError, match="has expired"):
            service.approve(rec.approval_id, approver=supervisor)

        store.save(rec)  # reset to pending
        with pytest.raises(ValueError, match="has expired"):
            service.reject(rec.approval_id, approver=supervisor)

        # 5. Attempt approve/reject on non-pending
        clock = ControlledClock()
        service = ApprovalService(store=store, clock=clock)
        rec2, _ = service.create_approval(
            request_id="req2",
            principal_id="user2",
            tool_name="tool2",
            action_name="action2",
            argument_hash="b" * 64,
            policy_version="1.0.0",
        )
        service.approve(rec2.approval_id, approver=supervisor)
        with pytest.raises(ValueError, match="Cannot approve request in 'APPROVED' status"):
            service.approve(rec2.approval_id, approver=supervisor)

        with pytest.raises(ValueError, match="Cannot reject request in 'APPROVED' status"):
            service.reject(rec2.approval_id, approver=supervisor)

    def test_consume_validation_branches(self) -> None:
        clock = ControlledClock()
        service = ApprovalService(clock=clock)
        user = AuthenticatedPrincipal(principal_id="alice", permissions=frozenset({"tools:search"}))
        anon = AnonymousPrincipal()

        # 1. Missing / anonymous identity
        ok, reason, ev = service.consume("app1", anon, "tool", "act", "h" * 64, "1.0.0")
        assert not ok
        assert reason == REASON_DENY_MISSING_IDENTITY

        # 2. Unknown approval
        ok, reason, ev = service.consume("unknown_id", user, "tool", "act", "h" * 64, "1.0.0")
        assert not ok
        assert reason == REASON_DENY_APPROVAL_UNKNOWN

        # 3. Consume pending approval
        rec, _ = service.create_approval("req1", "alice", "tool", "act", "h" * 64, "1.0.0")
        ok, reason, ev = service.consume(rec.approval_id, user, "tool", "act", "h" * 64, "1.0.0")
        assert not ok
        assert reason == "DENY_APPROVAL_PENDING"

        # 4. Action mismatch and Policy mismatch
        supervisor = AuthenticatedPrincipal(principal_id="boss", roles=frozenset({"admin"}))
        service.approve(rec.approval_id, supervisor)

        ok, reason, ev = service.consume(
            rec.approval_id, user, "tool", "wrong_action", "h" * 64, "1.0.0"
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_ACTION_MISMATCH
        assert ev.event_type == "approval.failed"

        ok, reason, ev2 = service.consume(
            rec.approval_id, user, "tool", "act", "h" * 64, "different_policy_ver"
        )
        assert not ok
        assert reason == REASON_DENY_APPROVAL_POLICY_MISMATCH
        assert ev2.event_type == "approval.failed"
