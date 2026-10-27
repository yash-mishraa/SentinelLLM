"""FastAPI application factory and middleware configuration for SentinelLLM."""

import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from sentinelllm.api.config import ApiConfig
from sentinelllm.api.dependencies import (
    get_api_config,
    get_db_config,
    get_db_session,
    get_pdp,
    set_api_config,
)
from sentinelllm.api.routes import api_router
from sentinelllm.api.routes.health import get_health, get_readiness
from sentinelllm.api.schemas import HealthResponse, ReadyResponse
from sentinelllm.db.models import Base
from sentinelllm.policy.engine import PolicyDecisionPoint

logger = logging.getLogger("sentinelllm.api")


class PayloadTooLargeError(Exception):
    """Raised when streaming request body exceeds configured byte limit."""


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects request bodies exceeding configured byte limits with 413 Payload Too Large.

    Guarantees:
    1. Rejects requests where Content-Length exceeds max_size_bytes before reading the payload.
    2. Enforces streaming byte limits on chunked or spoofed requests during receive to prevent
       memory exhaustion denial of service.
    """

    def __init__(self, app: Any, max_size_bytes: int = 1_048_576) -> None:
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_size_bytes:
                    return self._create_413_response()
            except ValueError:
                pass

        bytes_received = 0
        original_receive = request.receive

        async def limited_receive() -> Any:
            nonlocal bytes_received
            message = await original_receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                bytes_received += len(body)
                if bytes_received > self.max_size_bytes:
                    raise PayloadTooLargeError()
            return message

        request._receive = limited_receive

        try:
            return await call_next(request)  # type: ignore[no-any-return]
        except PayloadTooLargeError:
            return self._create_413_response()

    def _create_413_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={
                "error": "Payload too large",
                "detail": (
                    f"Request body exceeds maximum allowed size of {self.max_size_bytes} bytes."
                ),
                "request_id": None,
            },
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle manager handling startup initialization and graceful shutdown."""
    api_config = get_api_config()
    db_config = get_db_config()
    engine = db_config.create_engine()

    # Security Invariant:
    # In production, never auto-create tables or run schema migrations on worker startup.
    # Migrations must execute as an explicit standalone pre-deployment release task.
    if api_config.environment != "production" and db_config.database_url.startswith("sqlite"):
        try:
            Base.metadata.create_all(engine)
        except Exception as e:
            # Multi-worker concurrency safety for SQLite: ignore table-exists race
            if "already exists" not in str(e).lower():
                raise
        logger.info("SentinelLLM Development: Schema tables verified for local SQLite database.")
    else:
        logger.info(
            "SentinelLLM REST Gateway initialized with database at %s", db_config.get_safe_url()
        )

    yield

    # Graceful shutdown: release database connection pools
    engine.dispose()
    logger.info("SentinelLLM REST Gateway shut down cleanly.")


def create_app(config: ApiConfig | None = None) -> FastAPI:
    """FastAPI application factory."""
    active_config = config or get_api_config()
    set_api_config(active_config)

    app = FastAPI(
        title="SentinelLLM Security Gateway API",
        description=(
            "Runtime security controls, prompt-injection defense, and policy enforcement "
            "for LLM applications and autonomous AI agents."
        ),
        version="1.0.0rc1",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 1. Request Body Size Limit Middleware
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_size_bytes=active_config.max_request_size_bytes,
    )

    # 2. Restrictive CORS Middleware (No wildcard origins when credentials enabled)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # 3. Global Exception Handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": str(exc.detail) if isinstance(exc.detail, str) else "HTTP Exception",
                "detail": exc.detail,
                "request_id": getattr(request.state, "request_id", None),
            },
            headers=exc.headers or {},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Sanitize validation errors to prevent leaking raw user inputs or sensitive payloads
        sanitized_errors = []
        for error in exc.errors():
            sanitized_errors.append(
                {
                    "loc": list(error.get("loc", [])),
                    "msg": error.get("msg"),
                    "type": error.get("type"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation Error",
                "detail": sanitized_errors,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled server exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "detail": "An internal security or processing error occurred.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    # 4. Mount API Routes
    app.include_router(api_router)

    # 5. Root Liveness and Readiness Probes (Kubernetes / Cloud Run / Container Orchestration)
    @app.get(
        "/healthz",
        response_model=HealthResponse,
        tags=["System Health"],
        summary="Process Liveness Probe (Root)",
    )
    def root_healthz() -> HealthResponse:
        return get_health()

    @app.get(
        "/readyz",
        response_model=ReadyResponse,
        tags=["System Health"],
        summary="Service Readiness Probe (Root)",
    )
    def root_readyz(
        session: Session = Depends(get_db_session),
        pdp: PolicyDecisionPoint = Depends(get_pdp),
    ) -> ReadyResponse:
        return get_readiness(session=session, pdp=pdp)

    return app


# Default app instance for ASGI servers (e.g. uvicorn sentinelllm.api.app:app)
app = create_app()
