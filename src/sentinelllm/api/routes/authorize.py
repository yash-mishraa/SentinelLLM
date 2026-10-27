"""Policy decision and authorization endpoint."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from sentinelllm.api.dependencies import (
    check_rate_limit,
    get_pdp,
    get_tool_registry,
    require_permission,
)
from sentinelllm.api.schemas import AuthorizeRequest, AuthorizeResponse
from sentinelllm.contracts.decision import Decision
from sentinelllm.policy.engine import REASON_DENY_UNKNOWN_TOOL, PolicyDecisionPoint
from sentinelllm.policy.models import AuthorizationRequest
from sentinelllm.policy.principal import AuthenticatedPrincipal
from sentinelllm.tools.registry import ToolRegistry

router = APIRouter(prefix="/authorize", tags=["Policy Authorization"])


@router.post(
    "",
    response_model=AuthorizeResponse,
    summary="Evaluate Tool Action Policy",
    description=(
        "Evaluates proposed tool action against security rules and emits deterministic "
        "authorization decision."
    ),
    dependencies=[Depends(check_rate_limit)],
)
def evaluate_authorization(
    payload: AuthorizeRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission("authorize:run")),
    pdp: PolicyDecisionPoint = Depends(get_pdp),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
) -> AuthorizeResponse:
    """Evaluate whether principal is authorized to perform a proposed tool action."""
    # Identity Spoofing Defense: Callers cannot claim another identity in request body
    if payload.declared_principal_id and payload.declared_principal_id != principal.principal_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Identity spoofing rejected: declared identity '{payload.declared_principal_id}' "
                f"does not match authenticated credential '{principal.principal_id}'."
            ),
        )

    tool_spec = tool_registry.get_spec(payload.tool_name)
    if tool_spec is None:
        return AuthorizeResponse(
            decision="BLOCK",
            reason_code=REASON_DENY_UNKNOWN_TOOL,
            policy_version=pdp.policy_version,
            requires_approval=False,
            principal_id=principal.principal_id,
        )

    # Action Spoofing Defense: action_name must match tool specification
    if payload.action_name != tool_spec.action_identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Action spoofing rejected: declared action '{payload.action_name}' "
                f"does not match tool specification action '{tool_spec.action_identifier}'."
            ),
        )

    resource = tool_spec.resource_classification

    auth_req = AuthorizationRequest(
        request_id=uuid4().hex,
        principal=principal,
        action=payload.action_name,
        resource=resource,
        metadata=payload.arguments,
    )

    decision_record = pdp.evaluate(auth_req)
    requires_approval = decision_record.decision == Decision.REVIEW

    return AuthorizeResponse(
        decision=decision_record.decision.value.upper(),
        reason_code=decision_record.reason,
        policy_version=pdp.policy_version,
        requires_approval=requires_approval,
        principal_id=principal.principal_id,
    )
