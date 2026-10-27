"""Content inspection and security detection endpoint."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from sentinelllm.api.dependencies import (
    check_rate_limit,
    get_audit_store,
    get_orchestrator,
    get_pdp,
    require_permission,
)
from sentinelllm.api.schemas import InspectRequest, InspectResponse, SecurityFindingSchema
from sentinelllm.contracts.context import RequestContext
from sentinelllm.contracts.decision import Severity
from sentinelllm.contracts.messages import parse_untrusted_content
from sentinelllm.db.audit_store import SqlAuditStore
from sentinelllm.orchestrator import LifecycleOrchestrator
from sentinelllm.policy.engine import PolicyDecisionPoint
from sentinelllm.policy.principal import AuthenticatedPrincipal

router = APIRouter(prefix="/inspect", tags=["Inspection & Detection"])


@router.post(
    "",
    response_model=InspectResponse,
    summary="Scan Inbound Content",
    description=(
        "Analyzes untrusted content through heuristic detectors and returns security findings."
    ),
    dependencies=[Depends(check_rate_limit)],
)
def inspect_content(
    payload: InspectRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission("inspect:run")),
    orchestrator: LifecycleOrchestrator = Depends(get_orchestrator),
    pdp: PolicyDecisionPoint = Depends(get_pdp),
    audit_store: SqlAuditStore = Depends(get_audit_store),
) -> InspectResponse:
    """Scan inbound user prompts or contextual chunks for prompt injection and canary leaks."""
    prov_norm = payload.source_type.strip().lower()

    if prov_norm in ("retrieved_document", "retrieved_chunk"):
        raw_dict = {
            "content": payload.content,
            "provenance": "retrieved_document",
            "chunk_id": payload.metadata.get("chunk_id", "chunk_inspect"),
            "metadata": payload.metadata,
        }
    elif prov_norm in ("external_tool", "tool_output"):
        raw_dict = {
            "content": payload.content,
            "provenance": "external_tool",
            "tool_name": payload.metadata.get("tool_name", "tool_inspect"),
            "metadata": payload.metadata,
        }
    else:
        raw_dict = {
            "content": payload.content,
            "provenance": prov_norm,
            "metadata": payload.metadata,
        }

    try:
        content_item = parse_untrusted_content(raw_dict)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        ) from err

    req_id = uuid4().hex
    context = RequestContext(
        request_id=req_id,
        items=(content_item,),
    )

    lifecycle_res = orchestrator.process(context)
    findings = lifecycle_res.findings

    # Persist audit telemetry emitted during orchestration
    if lifecycle_res.audit_events:
        audit_store.save_batch(lifecycle_res.audit_events)

    findings_schema = [
        SecurityFindingSchema(
            source=f.source,
            category=f.category,
            severity=f.severity.value,
            explanation=f.explanation,
            metadata=f.metadata,
        )
        for f in findings
    ]

    has_high_or_critical = any(f.severity in (Severity.CRITICAL, Severity.HIGH) for f in findings)
    decision_label = "BLOCK" if has_high_or_critical else "ALLOW"
    is_blocked = has_high_or_critical

    return InspectResponse(
        request_id=req_id,
        decision=decision_label,
        is_safe=not is_blocked and len(findings) == 0,
        blocked=is_blocked,
        findings_count=len(findings_schema),
        findings=findings_schema,
    )
