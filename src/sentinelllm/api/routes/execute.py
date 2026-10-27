"""Tool authorization and safe proxy execution endpoint."""

import time

from fastapi import APIRouter, Depends, HTTPException, status

from sentinelllm.api.dependencies import (
    check_rate_limit,
    get_audit_store,
    get_current_principal,
    get_pep,
)
from sentinelllm.api.schemas import ExecuteRequest, ExecuteResponse
from sentinelllm.db.audit_store import SqlAuditStore
from sentinelllm.policy.principal import AuthenticatedPrincipal
from sentinelllm.tools.pep import PolicyEnforcementPoint

router = APIRouter(prefix="/execute", tags=["Tool Execution Proxy"])


@router.post(
    "",
    response_model=ExecuteResponse,
    summary="Execute Protected Tool Action",
    description=(
        "Validates permissions, security findings, and single-use approvals "
        "before safely proxying tool execution."
    ),
    dependencies=[Depends(check_rate_limit)],
)
def execute_tool_action(
    payload: ExecuteRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    pep: PolicyEnforcementPoint = Depends(get_pep),
    audit_store: SqlAuditStore = Depends(get_audit_store),
) -> ExecuteResponse:
    """Safely execute a tool action through the Policy Enforcement Point."""
    # Identity Spoofing Defense
    if payload.declared_principal_id and payload.declared_principal_id != principal.principal_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Identity spoofing rejected: declared identity '{payload.declared_principal_id}' "
                f"does not match authenticated credential '{principal.principal_id}'."
            ),
        )

    start_time = time.perf_counter()
    pep_result = pep.invoke(
        tool_name=payload.tool_name,
        raw_arguments=payload.arguments,
        principal=principal,
        approval_id=payload.approval_id,
    )
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Persist PEP audit trail
    if pep_result.audit_events:
        audit_store.save_batch(pep_result.audit_events)

    app_id = pep_result.approval_id or payload.approval_id

    output_data = None
    if pep_result.output is not None:
        try:
            import json

            output_data = json.loads(pep_result.output.content)
        except Exception:
            output_data = pep_result.output.content

    return ExecuteResponse(
        status=pep_result.status.upper(),
        result=output_data,
        reason_code=pep_result.reason_code,
        approval_id=app_id,
        execution_time_ms=round(elapsed_ms, 2),
    )
