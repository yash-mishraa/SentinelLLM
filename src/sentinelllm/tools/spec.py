"""Tool specification and schema definitions for action-level authorization."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolSpec(BaseModel):
    """Immutable specification declaring a tool's security and execution attributes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    action_identifier: str = Field(min_length=1)
    resource_classification: str = Field(min_length=1)
    argument_schema: type[BaseModel]
    is_sensitive: bool = False
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
