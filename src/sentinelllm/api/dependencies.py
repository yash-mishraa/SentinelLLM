"""FastAPI dependency injection providers for SentinelLLM REST Gateway."""

from collections.abc import Callable, Generator

from fastapi import Depends, HTTPException, Request, Security, status
from sqlalchemy.orm import Session

from sentinelllm.api.auth import ApiKeyRegistry, api_key_header_scheme
from sentinelllm.api.config import ApiConfig
from sentinelllm.api.rate_limiter import BaseRateLimiter, InMemoryRateLimiter, SqlRateLimiter
from sentinelllm.approvals.service import ApprovalService
from sentinelllm.db.approval_store import SqlApprovalStore
from sentinelllm.db.audit_store import SqlAuditStore
from sentinelllm.db.config import DatabaseConfig
from sentinelllm.orchestrator import LifecycleOrchestrator
from sentinelllm.policy.engine import PolicyDecisionPoint
from sentinelllm.policy.principal import AuthenticatedPrincipal
from sentinelllm.tools.pep import PolicyEnforcementPoint
from sentinelllm.tools.registry import ToolRegistry

# Module-level singletons for performance and consistency
_global_api_config: ApiConfig | None = None
_global_api_key_registry: ApiKeyRegistry | None = None
_global_db_config: DatabaseConfig | None = None
_global_pdp: PolicyDecisionPoint | None = None
_global_orchestrator: LifecycleOrchestrator | None = None
_global_tool_registry: ToolRegistry | None = None
_global_rate_limiter: BaseRateLimiter | None = None


def get_api_config() -> ApiConfig:
    """Provide API configuration settings."""
    global _global_api_config
    if _global_api_config is None:
        _global_api_config = ApiConfig.from_env()
    return _global_api_config


def set_api_config(config: ApiConfig | None) -> None:
    """Override API configuration (used in tests)."""
    global _global_api_config
    _global_api_config = config


def get_db_config() -> DatabaseConfig:
    """Provide database engine configuration."""
    global _global_db_config
    if _global_db_config is None:
        _global_db_config = DatabaseConfig.from_env()
    return _global_db_config


def set_db_config(config: DatabaseConfig | None) -> None:
    """Override DB configuration (used in tests)."""
    global _global_db_config
    _global_db_config = config


def get_db_session(
    db_config: DatabaseConfig = Depends(get_db_config),
) -> Generator[Session, None, None]:
    """Yield a scoped database session with automatic commit/rollback and cleanup."""
    factory = db_config.create_session_factory()
    with factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def get_approval_store(
    session: Session = Depends(get_db_session),
    db_config: DatabaseConfig = Depends(get_db_config),
) -> SqlApprovalStore:
    """Provide SQL-backed approval store bound to the current database engine."""
    return SqlApprovalStore(db_config.create_session_factory())


def get_audit_store(
    session: Session = Depends(get_db_session),
    db_config: DatabaseConfig = Depends(get_db_config),
) -> SqlAuditStore:
    """Provide SQL-backed audit store bound to the current database engine."""
    return SqlAuditStore(db_config.create_session_factory())


def get_approval_service(
    approval_store: SqlApprovalStore = Depends(get_approval_store),
) -> ApprovalService:
    """Provide ApprovalService coordinating approval requests and consumption."""
    return ApprovalService(store=approval_store)


def get_orchestrator() -> LifecycleOrchestrator:
    """Provide the security lifecycle orchestrator."""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = LifecycleOrchestrator()
    return _global_orchestrator


def get_pdp() -> PolicyDecisionPoint:
    """Provide the Policy Decision Point."""
    global _global_pdp
    if _global_pdp is None:
        _global_pdp = PolicyDecisionPoint()
    return _global_pdp


def get_tool_registry() -> ToolRegistry:
    """Provide the ToolRegistry with registered simulated tools."""
    global _global_tool_registry
    if _global_tool_registry is None:
        _global_tool_registry = ToolRegistry.create_default_registry()
    return _global_tool_registry


def get_pep(
    pdp: PolicyDecisionPoint = Depends(get_pdp),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> PolicyEnforcementPoint:
    """Provide the Policy Enforcement Point bound to PDP, registry, and approval service."""
    return PolicyEnforcementPoint(
        pdp=pdp,
        registry=tool_registry,
        approval_service=approval_service,
    )


def get_api_key_registry(api_config: ApiConfig = Depends(get_api_config)) -> ApiKeyRegistry:
    """Provide the thread-safe API key registry."""
    global _global_api_key_registry
    if _global_api_key_registry is None:
        _global_api_key_registry = ApiKeyRegistry.create_default(
            api_keys_json=api_config.api_keys_json,
            is_production=(api_config.environment == "production"),
        )
    return _global_api_key_registry


def set_api_key_registry(registry: ApiKeyRegistry | None) -> None:
    """Override API key registry (used in tests)."""
    global _global_api_key_registry
    _global_api_key_registry = registry


def get_rate_limiter(
    api_config: ApiConfig = Depends(get_api_config),
    db_config: DatabaseConfig = Depends(get_db_config),
) -> BaseRateLimiter:
    """Provide the active rate limiter implementation."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        try:
            _global_rate_limiter = SqlRateLimiter(db_config.create_session_factory())
        except Exception:
            _global_rate_limiter = InMemoryRateLimiter()
    return _global_rate_limiter


def set_rate_limiter(limiter: BaseRateLimiter | None) -> None:
    """Override rate limiter (used in tests)."""
    global _global_rate_limiter
    _global_rate_limiter = limiter


def get_current_principal(
    api_key: str | None = Security(api_key_header_scheme),
    registry: ApiKeyRegistry = Depends(get_api_key_registry),
) -> AuthenticatedPrincipal:
    """Authenticate incoming HTTP request using X-API-Key header.

    Security Invariant:
    Caller identity is strictly resolved from verified cryptographic credentials.
    Caller-supplied bodies claiming identities or permissions are ignored.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide valid 'X-API-Key' request header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    principal = registry.lookup(api_key)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unrecognized API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return principal


def require_permission(
    permission: str,
) -> Callable[[AuthenticatedPrincipal], AuthenticatedPrincipal]:
    """Dependency factory enforcing explicit permission or admin role."""

    def _dependency(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if (
            principal.has_permission(permission)
            or principal.has_role("admin")
            or principal.has_permission("*")
        ):
            return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Principal '{principal.principal_id}' lacks required permission '{permission}'."
            ),
        )

    return _dependency


def require_role(role: str) -> Callable[[AuthenticatedPrincipal], AuthenticatedPrincipal]:
    """Dependency factory enforcing explicit role or admin role."""

    def _dependency(
        principal: AuthenticatedPrincipal = Depends(get_current_principal),
    ) -> AuthenticatedPrincipal:
        if principal.has_role(role) or principal.has_role("admin"):
            return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Principal '{principal.principal_id}' lacks required role '{role}'.",
        )

    return _dependency


def check_rate_limit(
    request: Request,
    api_config: ApiConfig = Depends(get_api_config),
    limiter: BaseRateLimiter = Depends(get_rate_limiter),
    registry: ApiKeyRegistry = Depends(get_api_key_registry),
) -> None:
    """Enforce rate limits per authenticated principal or client IP.

    Security Invariant:
    - Authenticated callers are rate-limited per verified principal_id.
    - Unauthenticated callers are rate-limited by direct client socket IP.
    - Spoofable headers (e.g. X-Forwarded-For) are never trusted for identity keys.
    """
    if not api_config.rate_limit_enabled:
        return

    raw_key = request.headers.get("X-API-Key")
    principal = registry.lookup(raw_key) if raw_key else None

    if principal:
        key = f"rate_limit:principal:{principal.principal_id}"
    else:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:ip:{client_ip}"

    allowed, _remaining, reset_after = limiter.check_rate_limit(
        key=key,
        max_requests=api_config.rate_limit_per_minute,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded. Maximum {api_config.rate_limit_per_minute} "
                "requests/minute allowed."
            ),
            headers={"Retry-After": str(max(1, int(reset_after)))},
        )
