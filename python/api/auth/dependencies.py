"""Auth dependencies for FastAPI endpoints.

Provides injectable dependencies for authentication and authorization:
- ``get_current_user``: extracts user from JWT (anonymous fallback in dev)
- ``require_auth``: rejects anonymous users
- ``require_admin``: requires admin role
- ``require_role(min_role)``: hierarchical role check
"""

import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from python.api.auth.jwt_handler import verify_token

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Role hierarchy: higher index = more privileged
ROLE_HIERARCHY = ["viewer", "analyst", "manager", "admin"]


@lru_cache(maxsize=1)
def _role_index_map() -> dict[str, int]:
    return {role: idx for idx, role in enumerate(ROLE_HIERARCHY)}


def _role_level(role: str) -> int:
    return _role_index_map().get(role, 0)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Extract and verify user from JWT token.

    Returns anonymous user dict when no token is provided (dev mode).
    """
    if credentials is None:
        logger.debug("No credentials provided — returning anonymous user.")
        return {
            "user_id": "anonymous",
            "email": "anonymous@enlace.dev",
            "tenant_id": "default",
            "role": "viewer",
            "full_name": "Anônimo",
            "anonymous": True,
        }

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": payload.get("sub", payload.get("user_id", "unknown")),
        "email": payload.get("email", ""),
        "tenant_id": payload.get("tenant_id", "default"),
        "role": payload.get("role", "viewer"),
        "full_name": payload.get("full_name", ""),
        "anonymous": False,
    }


async def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """Require authentication (anonymous allowed in dev mode)."""
    import os
    if user.get("anonymous") and os.getenv("DEV_MODE", "1") == "0":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: dict = Depends(require_auth)) -> dict:
    """Require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso de administrador necessário",
        )
    return user


def require_role(min_role: str):
    """Factory that returns a dependency requiring at least `min_role` privilege.

    Usage:
        @router.get("/endpoint")
        async def endpoint(user=Depends(require_role("manager"))):
            ...
    """
    min_level = _role_level(min_role)

    async def _check(user: dict = Depends(require_auth)) -> dict:
        user_level = _role_level(user.get("role", "viewer"))
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão insuficiente. Necessário: {min_role}",
            )
        return user

    return _check
