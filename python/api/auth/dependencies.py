"""Auth dependencies for FastAPI endpoints.

Provides injectable dependencies for authentication and authorization:
- ``get_current_user``: extracts user from JWT (anonymous fallback in dev)
- ``require_auth``: rejects anonymous users
- ``require_admin``: requires admin role
"""

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from python.api.auth.jwt_handler import verify_token

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Extract and verify user from JWT token.

    If a valid bearer token is provided, decodes and returns the user
    payload (``user_id``, ``email``, ``tenant_id``, ``role``).

    If no token is provided, returns a default anonymous user dict
    so that endpoints work during development without authentication.

    Args:
        credentials: HTTP Bearer credentials injected by FastAPI.

    Returns:
        User dict with keys: user_id, email, tenant_id, role, anonymous.
    """
    if credentials is None:
        logger.debug("No credentials provided — returning anonymous user.")
        return {
            "user_id": "anonymous",
            "email": "anonymous@enlace.dev",
            "tenant_id": "default",
            "role": "viewer",
            "anonymous": True,
        }

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": payload.get("sub", payload.get("user_id", "unknown")),
        "email": payload.get("email", ""),
        "tenant_id": payload.get("tenant_id", "default"),
        "role": payload.get("role", "viewer"),
        "anonymous": False,
    }


async def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """Require authentication (no anonymous access).

    Raises:
        HTTPException 401: If the user is anonymous.
    """
    if user.get("anonymous"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(user: dict = Depends(require_auth)) -> dict:
    """Require admin role.

    Raises:
        HTTPException 403: If the user does not have the admin role.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
