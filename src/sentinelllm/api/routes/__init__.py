"""API v1 router composition for SentinelLLM."""

from fastapi import APIRouter

from sentinelllm.api.routes.approvals import router as approvals_router
from sentinelllm.api.routes.audit import router as audit_router
from sentinelllm.api.routes.authorize import router as authorize_router
from sentinelllm.api.routes.benchmark import router as benchmark_router
from sentinelllm.api.routes.execute import router as execute_router
from sentinelllm.api.routes.health import router as health_router
from sentinelllm.api.routes.inspect import router as inspect_router
from sentinelllm.api.routes.tools import router as tools_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(inspect_router)
api_router.include_router(authorize_router)
api_router.include_router(execute_router)
api_router.include_router(tools_router)
api_router.include_router(approvals_router)
api_router.include_router(audit_router)
api_router.include_router(benchmark_router)

__all__ = ["api_router"]
