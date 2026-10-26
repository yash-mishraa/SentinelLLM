"""Simulated tools and synthetic data collections for secure evaluation."""

import json
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from sentinelllm.tools.spec import ToolSpec

# Synthetic datasets for isolated testing
_SYNTHETIC_DOCUMENTS: Final[list[dict[str, str]]] = [
    {
        "doc_id": "doc_001",
        "title": "Data Retention Policy",
        "content": "All customer records must be retained for 7 years per regulatory rules.",
    },
    {
        "doc_id": "doc_002",
        "title": "API Rate Limits",
        "content": "Standard API consumers are limited to 100 requests per minute.",
    },
    {
        "doc_id": "doc_003",
        "title": "Incident Escalation Guide",
        "content": "Security incidents must be escalated to the on-call engineer in 15 minutes.",
    },
]

_SYNTHETIC_CUSTOMERS: Final[dict[str, dict[str, str]]] = {
    "cust_001": {
        "customer_id": "cust_001",
        "name": "Jane Doe",
        "tier": "enterprise",
        "status": "active",
    },
    "cust_002": {
        "customer_id": "cust_002",
        "name": "Acme Widgets",
        "tier": "pro",
        "status": "active",
    },
    "cust_003": {
        "customer_id": "cust_003",
        "name": "Cyberdyne Systems",
        "tier": "enterprise",
        "status": "suspended",
    },
}


class SearchDocumentsArgs(BaseModel):
    """Arguments for the synthetic document search tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class ReadCustomerRecordArgs(BaseModel):
    """Arguments for reading a single synthetic customer record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    customer_id: str = Field(min_length=1)


class ExportCustomerRecordsArgs(BaseModel):
    """Arguments for exporting customer records."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: str = "json"
    destination: str = "synthetic_archive"


def execute_search_documents(args: BaseModel) -> str:
    """Execute simulated document search against synthetic collection."""
    if not isinstance(args, SearchDocumentsArgs):
        raise TypeError(f"Expected SearchDocumentsArgs, got {type(args).__name__}")

    q = args.query.lower()
    matches = [
        d for d in _SYNTHETIC_DOCUMENTS if q in d["title"].lower() or q in d["content"].lower()
    ]
    return json.dumps(matches[: args.limit])


def execute_read_customer_record(args: BaseModel) -> str:
    """Execute simulated single customer record retrieval."""
    if not isinstance(args, ReadCustomerRecordArgs):
        raise TypeError(f"Expected ReadCustomerRecordArgs, got {type(args).__name__}")

    record = _SYNTHETIC_CUSTOMERS.get(args.customer_id)
    if record is None:
        return json.dumps({"error": f"Customer '{args.customer_id}' not found."})
    return json.dumps(record)


def execute_export_customer_records(args: BaseModel) -> str:
    """Execute simulated bulk customer export."""
    if not isinstance(args, ExportCustomerRecordsArgs):
        raise TypeError(f"Expected ExportCustomerRecordsArgs, got {type(args).__name__}")

    return json.dumps(
        {
            "status": "exported",
            "count": len(_SYNTHETIC_CUSTOMERS),
            "format": args.format,
            "destination": args.destination,
            "records": list(_SYNTHETIC_CUSTOMERS.values()),
        }
    )


SPEC_SEARCH_DOCUMENTS: Final[ToolSpec] = ToolSpec(
    tool_name="search_documents",
    description="Search internal documentation and knowledge base articles.",
    action_identifier="tools:execute:search_documents",
    resource_classification="documents",
    argument_schema=SearchDocumentsArgs,
    is_sensitive=False,
    requires_approval=False,
)

SPEC_READ_CUSTOMER_RECORD: Final[ToolSpec] = ToolSpec(
    tool_name="read_customer_record",
    description="Read a single customer record by customer_id.",
    action_identifier="tools:execute:read_customer_record",
    resource_classification="customer_records",
    argument_schema=ReadCustomerRecordArgs,
    is_sensitive=True,
    requires_approval=False,
)

SPEC_EXPORT_CUSTOMER_RECORDS: Final[ToolSpec] = ToolSpec(
    tool_name="export_customer_records",
    description="Export customer records to a specified destination format.",
    action_identifier="tools:execute:export_customer_records",
    resource_classification="customer_records",
    argument_schema=ExportCustomerRecordsArgs,
    is_sensitive=True,
    requires_approval=True,
)
