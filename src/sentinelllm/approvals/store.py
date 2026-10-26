"""In-memory store for human approval requests."""

from sentinelllm.approvals.models import ApprovalRequest


class InMemoryApprovalStore:
    """Process-local, in-memory store for pending and resolved approval records.

    Limitations:
    This store resides strictly in local process memory and does not persist across
    process restarts or synchronize across distributed instances. For distributed
    deployments, substitute with an atomic distributed store (e.g., Redis or SQL database).
    """

    def __init__(self) -> None:
        self._records: dict[str, ApprovalRequest] = {}

    def save(self, record: ApprovalRequest) -> None:
        """Store or update an approval record."""
        self._records[record.approval_id] = record

    def get(self, approval_id: str) -> ApprovalRequest | None:
        """Retrieve an approval record by its unique identifier."""
        return self._records.get(approval_id)

    def list_all(self) -> list[ApprovalRequest]:
        """Return all approval records."""
        return list(self._records.values())

    def clear(self) -> None:
        """Clear all stored records (for testing)."""
        self._records.clear()
