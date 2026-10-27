"""Human approval lifecycle management endpoints."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sentinelllm.api.auth import verify_self_approval
from sentinelllm.api.dependencies import (
    check_rate_limit,
    get_approval_service,
    get_approval_store,
    get_audit_store,
    get_current_principal,
    get_pdp,
    get_tool_registry,
    require_permission,
)
from sentinelllm.api.schemas import (
    ApprovalListResponse,
    ApprovalResponse,
    ApproveActionRequest,
    CreateApprovalRequest,
    RejectActionRequest,
)
from sentinelllm.approvals.service import ApprovalService
from sentinelllm.db.approval_store import SqlApprovalStore
from sentinelllm.db.audit_store import SqlAuditStore
from sentinelllm.policy.engine import PolicyDecisionPoint
from sentinelllm.policy.principal import AuthenticatedPrincipal
from sentinelllm.tools.registry import ToolRegistry

router = APIRouter(prefix="/approvals", tags=["Human Approvals"])


@router.post(
    "",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Approval Request",
    description="Registers an action-level authorization request for supervisor review.",
    dependencies=[Depends(check_rate_limit)],
)
def create_approval_request(
    payload: CreateApprovalRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    approval_service: ApprovalService = Depends(get_approval_service),
    audit_store: SqlAuditStore = Depends(get_audit_store),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    pdp: PolicyDecisionPoint = Depends(get_pdp),
) -> ApprovalResponse:
    """Register an approval review request bound to the authenticated caller."""
    # Tool and Action Existence Validation
    tool_spec = tool_registry.get_spec(payload.tool_name)
    if tool_spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot request approval for unregistered tool '{payload.tool_name}'.",
        )
    if payload.action_name != tool_spec.action_identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Action mismatch: declared action '{payload.action_name}' does not "
                f"match registered tool action '{tool_spec.action_identifier}'."
            ),
        )
    if payload.policy_version != pdp.policy_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Policy version mismatch: active policy is '{pdp.policy_version}', "
                f"but request specified '{payload.policy_version}'."
            ),
        )

    record, audit_event = approval_service.create_approval(
        request_id=uuid4().hex,
        principal_id=principal.principal_id,
        tool_name=payload.tool_name,
        action_name=payload.action_name,
        argument_hash=payload.argument_hash,
        policy_version=payload.policy_version,
        ttl_seconds=payload.ttl_seconds,
    )
    audit_store.save(audit_event)

    return ApprovalResponse(
        approval_id=record.approval_id,
        request_id=record.request_id,
        principal_id=record.principal_id,
        tool_name=record.tool_name,
        action_name=record.action_name,
        argument_hash=record.argument_hash,
        policy_version=record.policy_version,
        status=record.status.value,
        created_at=record.created_at,
        expires_at=record.expires_at,
        reviewed_by=record.reviewed_by,
        reviewed_at=record.reviewed_at,
        rejection_reason=record.rejection_reason,
        consumed_at=record.consumed_at,
    )


@router.get(
    "",
    response_model=ApprovalListResponse,
    summary="List Approval Requests",
    description="Retrieves a paginated list of approval requests with caller isolation.",
    dependencies=[Depends(check_rate_limit)],
)
def list_approval_requests(
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    approval_store: SqlApprovalStore = Depends(get_approval_store),
) -> ApprovalListResponse:
    """List approval requests with role-based access control and tenant isolation."""
    has_mgmt = principal.has_permission("approvals:manage") or principal.has_role("admin")

    # Callers without approval management permissions can only view their own requests
    filter_principal = None if has_mgmt else principal.principal_id

    records = approval_store.query(
        status=status_filter,
        principal_id=filter_principal,
        limit=limit,
        offset=offset,
    )

    approvals = [
        ApprovalResponse(
            approval_id=r.approval_id,
            request_id=r.request_id,
            principal_id=r.principal_id,
            tool_name=r.tool_name,
            action_name=r.action_name,
            argument_hash=r.argument_hash,
            policy_version=r.policy_version,
            status=r.status.value,
            created_at=r.created_at,
            expires_at=r.expires_at,
            reviewed_by=r.reviewed_by,
            reviewed_at=r.reviewed_at,
            rejection_reason=r.rejection_reason,
            consumed_at=r.consumed_at,
        )
        for r in records
    ]

    return ApprovalListResponse(
        approvals=approvals,
        count=len(approvals),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{approval_id}",
    response_model=ApprovalResponse,
    summary="Get Approval Record",
    description="Retrieves status and metadata for a specific approval request.",
    dependencies=[Depends(check_rate_limit)],
)
def get_approval_request(
    approval_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    approval_store: SqlApprovalStore = Depends(get_approval_store),
) -> ApprovalResponse:
    """Retrieve an approval record with access control boundary."""
    record = approval_store.get(approval_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found.",
        )

    # Privacy / Authorization check: Only requester, supervisor, or admin can inspect
    is_owner = record.principal_id == principal.principal_id
    has_mgmt = principal.has_permission("approvals:manage") or principal.has_role("admin")

    if not is_owner and not has_mgmt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you are not authorized to view this approval request.",
        )

    return ApprovalResponse(
        approval_id=record.approval_id,
        request_id=record.request_id,
        principal_id=record.principal_id,
        tool_name=record.tool_name,
        action_name=record.action_name,
        argument_hash=record.argument_hash,
        policy_version=record.policy_version,
        status=record.status.value,
        created_at=record.created_at,
        expires_at=record.expires_at,
        reviewed_by=record.reviewed_by,
        reviewed_at=record.reviewed_at,
        rejection_reason=record.rejection_reason,
        consumed_at=record.consumed_at,
    )


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalResponse,
    summary="Authorize Pending Approval",
    description=(
        "Grants supervisor authorization for a sensitive action, strictly prohibiting "
        "self-approval."
    ),
    dependencies=[Depends(check_rate_limit)],
)
def approve_request(
    approval_id: str,
    payload: ApproveActionRequest,
    approver: AuthenticatedPrincipal = Depends(require_permission("approvals:manage")),
    approval_store: SqlApprovalStore = Depends(get_approval_store),
    approval_service: ApprovalService = Depends(get_approval_service),
    audit_store: SqlAuditStore = Depends(get_audit_store),
) -> ApprovalResponse:
    """Grant supervisor approval for a pending tool action."""
    record = approval_store.get(approval_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found.",
        )

    # Separation of Duties / Self-Approval Defense
    verify_self_approval(requester_id=record.principal_id, approver_id=approver.principal_id)

    try:
        updated_record, audit_event = approval_service.approve(approval_id, approver=approver)
        audit_store.save(audit_event)
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return ApprovalResponse(
        approval_id=updated_record.approval_id,
        request_id=updated_record.request_id,
        principal_id=updated_record.principal_id,
        tool_name=updated_record.tool_name,
        action_name=updated_record.action_name,
        argument_hash=updated_record.argument_hash,
        policy_version=updated_record.policy_version,
        status=updated_record.status.value,
        created_at=updated_record.created_at,
        expires_at=updated_record.expires_at,
        reviewed_by=updated_record.reviewed_by,
        reviewed_at=updated_record.reviewed_at,
        rejection_reason=updated_record.rejection_reason,
        consumed_at=updated_record.consumed_at,
    )


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject Pending Approval",
    description="Rejects an authorization request with an explicit supervisor reason.",
    dependencies=[Depends(check_rate_limit)],
)
def reject_request(
    approval_id: str,
    payload: RejectActionRequest,
    approver: AuthenticatedPrincipal = Depends(require_permission("approvals:manage")),
    approval_service: ApprovalService = Depends(get_approval_service),
    audit_store: SqlAuditStore = Depends(get_audit_store),
) -> ApprovalResponse:
    """Explicitly reject a pending approval request."""
    try:
        updated_record, audit_event = approval_service.reject(
            approval_id=approval_id,
            approver=approver,
            reason=payload.reason,
        )
        audit_store.save(audit_event)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return ApprovalResponse(
        approval_id=updated_record.approval_id,
        request_id=updated_record.request_id,
        principal_id=updated_record.principal_id,
        tool_name=updated_record.tool_name,
        action_name=updated_record.action_name,
        argument_hash=updated_record.argument_hash,
        policy_version=updated_record.policy_version,
        status=updated_record.status.value,
        created_at=updated_record.created_at,
        expires_at=updated_record.expires_at,
        reviewed_by=updated_record.reviewed_by,
        reviewed_at=updated_record.reviewed_at,
        rejection_reason=updated_record.rejection_reason,
        consumed_at=updated_record.consumed_at,
    )
