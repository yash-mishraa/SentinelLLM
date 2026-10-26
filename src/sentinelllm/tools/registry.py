"""Tool registry maintaining tool specifications and simulated execution handlers."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from sentinelllm.tools.simulated import (
    SPEC_EXPORT_CUSTOMER_RECORDS,
    SPEC_READ_CUSTOMER_RECORD,
    SPEC_SEARCH_DOCUMENTS,
    execute_export_customer_records,
    execute_read_customer_record,
    execute_search_documents,
)
from sentinelllm.tools.spec import ToolSpec


class ToolRegistry:
    """Registry managing available tool specifications and execution handlers."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable[[Any], str]] = {}

    def register(self, spec: ToolSpec, handler: Callable[[Any], str]) -> None:
        """Register a tool specification with its execution handler."""
        if not isinstance(spec, ToolSpec):
            raise TypeError(f"Expected ToolSpec, got {type(spec).__name__}")
        if not callable(handler):
            raise TypeError(f"Handler for tool '{spec.tool_name}' must be callable.")

        self._specs[spec.tool_name] = spec
        self._handlers[spec.tool_name] = handler

    def get_spec(self, tool_name: str) -> ToolSpec | None:
        """Look up tool specification by tool name."""
        return self._specs.get(tool_name)

    def execute(self, tool_name: str, args: BaseModel) -> str:
        """Execute a tool handler with validated arguments."""
        handler = self._handlers.get(tool_name)
        if handler is None:
            raise KeyError(f"No execution handler registered for tool '{tool_name}'")
        return handler(args)

    @classmethod
    def create_default_registry(cls) -> "ToolRegistry":
        """Instantiate a registry populated with default synthetic tools."""
        registry = cls()
        registry.register(SPEC_SEARCH_DOCUMENTS, execute_search_documents)
        registry.register(SPEC_READ_CUSTOMER_RECORD, execute_read_customer_record)
        registry.register(SPEC_EXPORT_CUSTOMER_RECORDS, execute_export_customer_records)
        return registry
