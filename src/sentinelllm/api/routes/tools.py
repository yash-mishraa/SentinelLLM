"""Tool catalog inspection route for discovering registered system tools."""

from fastapi import APIRouter, Depends

from sentinelllm.api.dependencies import (
    check_rate_limit,
    get_current_principal,
    get_tool_registry,
)
from sentinelllm.api.schemas import ToolSpecResponse
from sentinelllm.policy.principal import AuthenticatedPrincipal
from sentinelllm.tools.registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["Tool Catalog"])


@router.get(
    "",
    response_model=list[ToolSpecResponse],
    summary="List Registered Tools",
    description="Returns metadata, action identifiers, and argument schemas for registered tools.",
    dependencies=[Depends(check_rate_limit)],
)
def list_registered_tools(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> list[ToolSpecResponse]:
    """Retrieve all registered tool specifications."""
    specs = registry.list_specs()
    return [
        ToolSpecResponse(
            tool_name=spec.tool_name,
            description=spec.description,
            action_identifier=spec.action_identifier,
            resource_classification=spec.resource_classification,
            is_sensitive=spec.is_sensitive,
            requires_approval=spec.requires_approval,
            argument_schema=spec.argument_schema.model_json_schema(),
        )
        for spec in specs
    ]
