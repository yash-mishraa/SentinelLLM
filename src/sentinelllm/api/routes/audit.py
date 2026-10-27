"""Searchable audit trail query endpoint."""

from fastapi import APIRouter, Depends, Query

from sentinelllm.api.dependencies import check_rate_limit, get_audit_store, require_permission
from sentinelllm.api.schemas import AuditEventResponse, AuditQueryResponse
from sentinelllm.db.audit_store import SqlAuditStore
from sentinelllm.policy.principal import AuthenticatedPrincipal

router = APIRouter(prefix="/audit", tags=["Audit & Telemetry"])


@router.get(
    "",
    response_model=AuditQueryResponse,
    summary="Query Structured Audit Trail",
    description=(
        "Retrieves security telemetry events with filtering and pagination. "
        "Requires 'audit:read' permission."
    ),
    dependencies=[Depends(check_rate_limit)],
)
def query_audit_trail(
    request_id: str | None = Query(default=None, max_length=64),
    event_type: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(require_permission("audit:read")),
    audit_store: SqlAuditStore = Depends(get_audit_store),
) -> AuditQueryResponse:
    """Query structured audit logs with privacy preservation and pagination."""
    events = audit_store.query(
        request_id=request_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )

    event_responses = [
        AuditEventResponse(
            event_id=e.event_id,
            request_id=e.request_id,
            event_type=e.event_type,
            timestamp=e.timestamp,
            component=e.component,
            decision=e.decision.value if e.decision is not None else None,
            policy_version=e.policy_version,
            metadata=e.metadata,
        )
        for e in events
    ]

    return AuditQueryResponse(
        events=event_responses,
        count=len(event_responses),
        limit=limit,
        offset=offset,
    )
