"""Approval service coordinating the human authorization lifecycle."""

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sentinelllm.approvals.models import ApprovalRequest, ApprovalStatus
from sentinelllm.approvals.store import InMemoryApprovalStore
from sentinelllm.contracts.audit import AuditEvent
from sentinelllm.contracts.decision import Decision
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
    REASON_DENY_MISSING_IDENTITY,
)
from sentinelllm.policy.principal import AuthenticatedPrincipal


class ApprovalService:
    """Service governing human approval creation, review, and single-use consumption.

    Security Invariants:
    1. Approvals are single-use and expire deterministically.
    2. Approvals are cryptographically bound to the exact principal, tool, action,
       canonical argument digest, and policy version.
    3. An approval can only be granted by an authenticated principal with explicit
       approval permissions—never by prompt text, metadata, or tool outputs.
    4. Audit records contain only safe metadata hashes; raw arguments and customer
       records are strictly excluded.
    """

    def __init__(
        self,
        store: InMemoryApprovalStore | None = None,
        clock: Callable[[], datetime] | None = None,
        default_ttl_seconds: int = 300,
        required_approval_permission: str = "approvals:manage",
        component_name: str = "approval_service",
    ) -> None:
        self.store = store if store is not None else InMemoryApprovalStore()
        self.clock = clock if clock is not None else (lambda: datetime.now(UTC))
        self.default_ttl_seconds = default_ttl_seconds
        self.required_approval_permission = required_approval_permission
        self.component_name = component_name
        self._lock = threading.RLock()

    def create_approval(
        self,
        request_id: str,
        principal_id: str,
        tool_name: str,
        action_name: str,
        argument_hash: str,
        policy_version: str,
        ttl_seconds: int | None = None,
    ) -> tuple[ApprovalRequest, AuditEvent]:
        """Create a pending approval request."""
        with self._lock:
            now = self.clock()
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
            expires_at = now + timedelta(seconds=ttl)
            approval_id = uuid4().hex

            record = ApprovalRequest(
                approval_id=approval_id,
                request_id=request_id,
                principal_id=principal_id,
                tool_name=tool_name,
                action_name=action_name,
                argument_hash=argument_hash,
                policy_version=policy_version,
                status=ApprovalStatus.PENDING,
                created_at=now,
                expires_at=expires_at,
            )
            self.store.save(record)

            audit_event = AuditEvent(
                request_id=request_id,
                event_type="approval.created",
                component=self.component_name,
                decision=Decision.REVIEW,
                policy_version=policy_version,
                metadata={
                    "approval_id": approval_id,
                    "principal_id": principal_id,
                    "tool_name": tool_name,
                    "action_name": action_name,
                    "argument_hash": argument_hash,
                    "status": ApprovalStatus.PENDING.value,
                },
            )
            return record, audit_event

    def approve(
        self,
        approval_id: str,
        approver: AuthenticatedPrincipal,
    ) -> tuple[ApprovalRequest, AuditEvent]:
        """Authorize a pending approval request."""
        with self._lock:
            # 1. Authorize approver
            if not isinstance(approver, AuthenticatedPrincipal) or not approver.is_authenticated:
                raise PermissionError("Approver must be an authenticated principal.")

            if not (
                approver.has_permission(self.required_approval_permission)
                or approver.has_role("admin")
            ):
                raise PermissionError(
                    f"Principal '{approver.principal_id}' lacks permission "
                    f"'{self.required_approval_permission}'."
                )

            # 2. Retrieve record
            record = self.store.get(approval_id)
            if record is None:
                raise KeyError(f"Approval request '{approval_id}' not found.")

            now = self.clock()

            # 3. Expiry check
            if now >= record.expires_at:
                expired_record = record.model_copy(update={"status": ApprovalStatus.EXPIRED})
                self.store.save(expired_record)
                raise ValueError(f"Approval request '{approval_id}' has expired.")

            # 4. Status check
            if record.status != ApprovalStatus.PENDING:
                raise ValueError(f"Cannot approve request in '{record.status.value}' status.")

            # 5. Transition to APPROVED
            approved_record = record.model_copy(
                update={
                    "status": ApprovalStatus.APPROVED,
                    "reviewed_by": approver.principal_id,
                    "reviewed_at": now,
                }
            )
            self.store.save(approved_record)

            audit_event = AuditEvent(
                request_id=record.request_id,
                event_type="approval.approved",
                component=self.component_name,
                decision=Decision.ALLOW,
                policy_version=record.policy_version,
                metadata={
                    "approval_id": approval_id,
                    "approver_id": approver.principal_id,
                    "status": ApprovalStatus.APPROVED.value,
                },
            )
            return approved_record, audit_event

    def reject(
        self,
        approval_id: str,
        approver: AuthenticatedPrincipal,
        reason: str = "Supervisor rejected action",
    ) -> tuple[ApprovalRequest, AuditEvent]:
        """Explicitly reject a pending approval request."""
        with self._lock:
            if not isinstance(approver, AuthenticatedPrincipal) or not approver.is_authenticated:
                raise PermissionError("Approver must be an authenticated principal.")

            if not (
                approver.has_permission(self.required_approval_permission)
                or approver.has_role("admin")
            ):
                raise PermissionError(
                    f"Principal '{approver.principal_id}' lacks permission "
                    f"'{self.required_approval_permission}'."
                )

            record = self.store.get(approval_id)
            if record is None:
                raise KeyError(f"Approval request '{approval_id}' not found.")

            now = self.clock()

            if now >= record.expires_at:
                expired_record = record.model_copy(update={"status": ApprovalStatus.EXPIRED})
                self.store.save(expired_record)
                raise ValueError(f"Approval request '{approval_id}' has expired.")

            if record.status != ApprovalStatus.PENDING:
                raise ValueError(f"Cannot reject request in '{record.status.value}' status.")

            rejected_record = record.model_copy(
                update={
                    "status": ApprovalStatus.REJECTED,
                    "reviewed_by": approver.principal_id,
                    "reviewed_at": now,
                    "rejection_reason": reason,
                }
            )
            self.store.save(rejected_record)

            audit_event = AuditEvent(
                request_id=record.request_id,
                event_type="approval.rejected",
                component=self.component_name,
                decision=Decision.BLOCK,
                policy_version=record.policy_version,
                metadata={
                    "approval_id": approval_id,
                    "approver_id": approver.principal_id,
                    "status": ApprovalStatus.REJECTED.value,
                    "reason": reason,
                },
            )
            return rejected_record, audit_event

    def consume(
        self,
        approval_id: str,
        principal: AuthenticatedPrincipal | None,
        tool_name: str,
        action_name: str,
        argument_hash: str,
        policy_version: str,
    ) -> tuple[bool, str, AuditEvent]:
        """Validate and atomically consume an approved action.

        Returns:
            Tuple of (success_bool, reason_code, audit_event).
        """
        with self._lock:
            now = self.clock()
            req_id = "unknown"

            # 1. Identity validation
            if principal is None or not principal.is_authenticated:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_MISSING_IDENTITY,
                    },
                )
                return False, REASON_DENY_MISSING_IDENTITY, fail_event

            # 2. Record lookup
            record = self.store.get(approval_id)
            if record is None:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_UNKNOWN,
                    },
                )
                return False, REASON_DENY_APPROVAL_UNKNOWN, fail_event

            req_id = record.request_id

            # 3. Expiry validation
            if now >= record.expires_at and record.status in (
                ApprovalStatus.PENDING,
                ApprovalStatus.APPROVED,
            ):
                expired_record = record.model_copy(update={"status": ApprovalStatus.EXPIRED})
                self.store.save(expired_record)
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.expired",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    policy_version=record.policy_version,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_EXPIRED,
                    },
                )
                return False, REASON_DENY_APPROVAL_EXPIRED, fail_event

            # 4. Status validation
            if record.status == ApprovalStatus.PENDING:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={"approval_id": approval_id, "reason_code": "DENY_APPROVAL_PENDING"},
                )
                return False, "DENY_APPROVAL_PENDING", fail_event

            if record.status == ApprovalStatus.REJECTED:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_REJECTED,
                    },
                )
                return False, REASON_DENY_APPROVAL_REJECTED, fail_event

            if record.status == ApprovalStatus.CONSUMED:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_ALREADY_CONSUMED,
                    },
                )
                return False, REASON_DENY_APPROVAL_ALREADY_CONSUMED, fail_event

            if record.status == ApprovalStatus.EXPIRED:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_EXPIRED,
                    },
                )
                return False, REASON_DENY_APPROVAL_EXPIRED, fail_event

            # 5. Exact request binding checks
            if record.principal_id != principal.principal_id:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH,
                    },
                )
                return False, REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH, fail_event

            if record.tool_name != tool_name:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_TOOL_MISMATCH,
                    },
                )
                return False, REASON_DENY_APPROVAL_TOOL_MISMATCH, fail_event

            if record.action_name != action_name:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_ACTION_MISMATCH,
                    },
                )
                return False, REASON_DENY_APPROVAL_ACTION_MISMATCH, fail_event

            if record.argument_hash != argument_hash:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH,
                    },
                )
                return False, REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH, fail_event

            if record.policy_version != policy_version:
                fail_event = AuditEvent(
                    request_id=req_id,
                    event_type="approval.failed",
                    component=self.component_name,
                    decision=Decision.BLOCK,
                    metadata={
                        "approval_id": approval_id,
                        "reason_code": REASON_DENY_APPROVAL_POLICY_MISMATCH,
                    },
                )
                return False, REASON_DENY_APPROVAL_POLICY_MISMATCH, fail_event

            # 6. Consume approval atomically
            consumed_record = record.model_copy(
                update={"status": ApprovalStatus.CONSUMED, "consumed_at": now}
            )
            self.store.save(consumed_record)

            consumed_event = AuditEvent(
                request_id=req_id,
                event_type="approval.consumed",
                component=self.component_name,
                decision=Decision.ALLOW,
                policy_version=record.policy_version,
                metadata={
                    "approval_id": approval_id,
                    "principal_id": principal.principal_id,
                    "status": ApprovalStatus.CONSUMED.value,
                },
            )
            return True, "APPROVAL_CONSUMED", consumed_event
