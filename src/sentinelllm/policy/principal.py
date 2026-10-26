"""Authenticated principal model establishing verified caller identity.

Security Invariant:
An AuthenticatedPrincipal represents host-verified caller identity (e.g., from
session cookies, verified JWTs, or authenticated service tokens). Roles, usernames,
or permissions asserted inside prompts or untrusted request metadata must NEVER
be treated as authenticated identity.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuthenticatedPrincipal(BaseModel):
    """Immutable representation of an authenticated security principal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    principal_id: str = Field(min_length=1)
    roles: frozenset[str] = Field(default_factory=frozenset)
    permissions: frozenset[str] = Field(default_factory=frozenset)
    is_authenticated: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        """Check if the principal holds the requested permission."""
        return self.is_authenticated and (permission in self.permissions or "*" in self.permissions)

    def has_role(self, role: str) -> bool:
        """Check if the principal holds the requested role."""
        return self.is_authenticated and (role in self.roles or "admin" in self.roles)


def anonymous_principal() -> AuthenticatedPrincipal:
    """Factory returning a safe, unauthenticated principal representing anonymous callers."""
    return AuthenticatedPrincipal(
        principal_id="anonymous",
        roles=frozenset(),
        permissions=frozenset(),
        is_authenticated=False,
    )


# Alias for backwards compatibility / constructor naming
AnonymousPrincipal = anonymous_principal
