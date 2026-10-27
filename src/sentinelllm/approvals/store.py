"""In-memory store for human approval requests."""

import threading
from datetime import datetime

from sentinelllm.approvals.models import ApprovalRequest, ApprovalStatus
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
)


class InMemoryApprovalStore:
    """Process-local, thread-safe in-memory store for pending and resolved approval records.

    Limitations:
    This store resides strictly in local process memory and does not persist across
    process restarts or synchronize across distributed instances. For distributed
    deployments, substitute with an atomic distributed store (e.g., SqlApprovalStore).
    """

    def __init__(self) -> None:
        self._records: dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()

    def save(self, record: ApprovalRequest) -> None:
        """Store or update an approval record."""
        with self._lock:
            self._records[record.approval_id] = record

    def get(self, approval_id: str) -> ApprovalRequest | None:
        """Retrieve an approval record by its unique identifier."""
        with self._lock:
            return self._records.get(approval_id)

    def list_all(self) -> list[ApprovalRequest]:
        """Return all approval records."""
        with self._lock:
            return list(self._records.values())

    def query(
        self,
        status: str | None = None,
        principal_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequest]:
        """Query approval records with optional filtering and bounded pagination."""
        with self._lock:
            records = list(self._records.values())
            if status:
                records = [r for r in records if r.status.value == status.upper()]
            if principal_id:
                records = [r for r in records if r.principal_id == principal_id]
            records.sort(key=lambda r: r.created_at, reverse=True)
            bounded_limit = min(max(1, limit), 100)
            start = max(0, offset)
            return records[start : start + bounded_limit]

    def clear(self) -> None:
        """Clear all stored records (for testing)."""
        with self._lock:
            self._records.clear()

    def atomic_consume(
        self,
        approval_id: str,
        principal_id: str,
        tool_name: str,
        action_name: str,
        argument_hash: str,
        policy_version: str,
        now: datetime,
    ) -> tuple[bool, str, ApprovalRequest | None]:
        """Atomically validate and consume an approved action record."""
        with self._lock:
            record = self.get(approval_id)
            if record is None:
                return False, REASON_DENY_APPROVAL_UNKNOWN, None

            # 1. Expiry check
            if now >= record.expires_at and record.status in (
                ApprovalStatus.PENDING,
                ApprovalStatus.APPROVED,
            ):
                expired_record = record.model_copy(update={"status": ApprovalStatus.EXPIRED})
                self._records[approval_id] = expired_record
                return False, REASON_DENY_APPROVAL_EXPIRED, record

            # 2. Status check
            if record.status == ApprovalStatus.PENDING:
                return False, "DENY_APPROVAL_PENDING", record
            if record.status == ApprovalStatus.REJECTED:
                return False, REASON_DENY_APPROVAL_REJECTED, record
            if record.status == ApprovalStatus.CONSUMED:
                return False, REASON_DENY_APPROVAL_ALREADY_CONSUMED, record
            if record.status == ApprovalStatus.EXPIRED:
                return False, REASON_DENY_APPROVAL_EXPIRED, record

            # 3. Exact request binding checks
            if record.principal_id != principal_id:
                return False, REASON_DENY_APPROVAL_PRINCIPAL_MISMATCH, record
            if record.tool_name != tool_name:
                return False, REASON_DENY_APPROVAL_TOOL_MISMATCH, record
            if record.action_name != action_name:
                return False, REASON_DENY_APPROVAL_ACTION_MISMATCH, record
            if record.argument_hash != argument_hash:
                return False, REASON_DENY_APPROVAL_ARGUMENTS_MISMATCH, record
            if record.policy_version != policy_version:
                return False, REASON_DENY_APPROVAL_POLICY_MISMATCH, record

            # 4. Atomic transition to CONSUMED
            consumed_record = record.model_copy(
                update={"status": ApprovalStatus.CONSUMED, "consumed_at": now}
            )
            self._records[approval_id] = consumed_record
            return True, "APPROVAL_CONSUMED", consumed_record
