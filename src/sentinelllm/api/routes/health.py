"""Health and readiness endpoints for the SentinelLLM REST Gateway."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from sentinelllm.api.dependencies import get_db_session, get_pdp
from sentinelllm.api.schemas import HealthResponse, ReadyResponse
from sentinelllm.policy.engine import PolicyDecisionPoint

router = APIRouter(tags=["System Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Process Liveness Probe",
    description="Returns lightweight process health status and runtime version.",
)
def get_health() -> HealthResponse:
    """Unauthenticated health endpoint for orchestration liveness checks."""
    return HealthResponse(
        status="ok",
        version="1.0.0rc1",
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Service Readiness Probe",
    description="Verifies database connectivity and policy engine initialization.",
)
def get_readiness(
    session: Session = Depends(get_db_session),
    pdp: PolicyDecisionPoint = Depends(get_pdp),
) -> ReadyResponse:
    """Readiness probe ensuring backend dependencies and policy engine are functional."""
    db_ok = False
    try:
        session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    pdp_ok = pdp is not None and bool(pdp.policy_version)

    if not db_ok or not pdp_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "database_connected": db_ok,
                "policy_engine_ready": pdp_ok,
            },
        )

    return ReadyResponse(
        status="ready",
        database_connected=db_ok,
        policy_engine_ready=pdp_ok,
        timestamp=datetime.now(UTC),
    )
