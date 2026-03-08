"""
ENLACE Auth Router

Authentication and user management endpoints. Provides login, registration,
and user profile retrieval. Uses JWT tokens for session management.

In development mode, login accepts any email/password combination and
generates a valid token. In production, this would integrate with a
proper user database and password hashing.
"""

import dataclasses
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from python.api.auth.jwt_handler import create_access_token
from python.api.auth.dependencies import get_current_user, require_auth
from python.api.auth.tenant import create_tenant, get_tenant, Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TokenRequest(BaseModel):
    """Login request body."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Login response with JWT token."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    tenant_id: str
    role: str


class RegisterRequest(BaseModel):
    """Registration request body."""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")
    name: str = Field(..., min_length=1, description="User display name")
    organization: str = Field(..., min_length=1, description="Organization / ISP name")
    state_code: Optional[str] = Field(None, min_length=2, max_length=2, description="Primary state code")


class RegisterResponse(BaseModel):
    """Registration response."""
    user_id: str
    email: str
    tenant_id: str
    organization: str
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    """User profile response."""
    user_id: str
    email: str
    tenant_id: str
    role: str
    anonymous: bool
    tenant: Optional[dict] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tenant_to_dict(tenant: Tenant) -> dict:
    """Convert a Tenant dataclass to a dict."""
    if dataclasses.is_dataclass(tenant) and not isinstance(tenant, type):
        return {f.name: getattr(tenant, f.name) for f in dataclasses.fields(tenant)}
    return {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(request: TokenRequest):
    """Authenticate and return a JWT token.

    In development mode (DEV_MODE=1 or default), accepts any email/password.
    In production (DEV_MODE=0), rejects all logins until a real user store
    is integrated.
    """
    import os

    dev_mode = os.getenv("DEV_MODE", "1").strip().lower() in ("1", "true", "yes")

    if not dev_mode:
        raise HTTPException(
            status_code=501,
            detail="Production authentication not configured. Set DEV_MODE=1 for development.",
        )

    logger.info(f"Login attempt for: {request.email} (dev mode)")

    # Derive a stable user_id from email for consistency
    user_id = request.email.split("@")[0].replace(".", "_")

    # Check if user has a tenant, default otherwise
    tenant_id = "default"

    token_data = {
        "sub": user_id,
        "email": request.email,
        "tenant_id": tenant_id,
        "role": "admin",  # Development default
    }

    access_token = create_access_token(data=token_data)

    logger.info(f"Login successful for: {request.email} (user_id={user_id})")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user_id,
        email=request.email,
        tenant_id=tenant_id,
        role="admin",
    )


@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest):
    """Register a new user and create a tenant for the organization.

    Creates a new tenant for the organization and returns a JWT token
    for immediate API access.
    """
    logger.info(f"Registration attempt: {request.email}, org={request.organization}")

    # Create a tenant for the organization
    try:
        tenant = create_tenant(
            name=request.organization,
            country_code="BR",
            primary_state=request.state_code,
            plan="free",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Derive user_id from email
    user_id = request.email.split("@")[0].replace(".", "_")

    # Create access token
    token_data = {
        "sub": user_id,
        "email": request.email,
        "tenant_id": tenant.id,
        "role": "admin",  # First user of a tenant is admin
    }

    access_token = create_access_token(data=token_data)

    logger.info(
        f"Registration successful: user={user_id}, tenant={tenant.id}, org={request.organization}"
    )

    return RegisterResponse(
        user_id=user_id,
        email=request.email,
        tenant_id=tenant.id,
        organization=request.organization,
        access_token=access_token,
        token_type="bearer",
    )


@router.get("/me", response_model=UserProfile)
async def get_me(user: dict = Depends(require_auth)):
    """Get current user profile.

    Returns the authenticated user's profile including tenant information.
    Requires a valid JWT token — returns 401 if unauthenticated.
    """
    tenant_dict = None
    tenant_id = user.get("tenant_id")
    if tenant_id:
        tenant = get_tenant(tenant_id)
        if tenant is not None:
            tenant_dict = _tenant_to_dict(tenant)

    return UserProfile(
        user_id=user.get("user_id", "unknown"),
        email=user.get("email", ""),
        tenant_id=user.get("tenant_id", "default"),
        role=user.get("role", "viewer"),
        anonymous=user.get("anonymous", True),
        tenant=tenant_dict,
    )
