"""In-memory store for human approval requests."""

import threading

from sentinelllm.approvals.models import ApprovalRequest


class InMemoryApprovalStore:
    """Process-local, thread-safe in-memory store for pending and resolved approval records.

    Limitations:
    This store resides strictly in local process memory and does not persist across
    process restarts or synchronize across distributed instances. For distributed
    deployments, substitute with an atomic distributed store (e.g., Redis or SQL database).
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

    def clear(self) -> None:
        """Clear all stored records (for testing)."""
        with self._lock:
            self._records.clear()
