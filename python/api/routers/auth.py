"""
ENLACE Auth Router

Authentication and user management endpoints with real database backing.
Uses bcrypt password hashing and JWT tokens with persistent user records.
Dev mode auto-creates user on first login.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from passlib.context import CryptContext

from python.api.auth.jwt_handler import create_access_token
from python.api.auth.dependencies import get_current_user, require_auth
from python.api.auth.tenant import create_tenant, get_tenant, Tenant
from python.api.database import get_db
from python.api.models.orm import User
import dataclasses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEV_MODE = os.getenv("DEV_MODE", "1").strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class TokenRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    tenant_id: str
    role: str
    full_name: str


class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")
    name: str = Field(..., min_length=1, description="User display name")
    organization: str = Field(..., min_length=1, description="Organization / ISP name")
    state_code: Optional[str] = Field(None, min_length=2, max_length=2)


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    tenant_id: str
    organization: str
    access_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    tenant_id: str
    role: str
    anonymous: bool
    is_active: bool = True
    preferences: dict = {}
    tenant: Optional[dict] = None


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    preferences: Optional[dict] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tenant_to_dict(tenant: Tenant) -> dict:
    if dataclasses.is_dataclass(tenant) and not isinstance(tenant, type):
        return {f.name: getattr(tenant, f.name) for f in dataclasses.fields(tenant)}
    return {}


def _make_token(user: User) -> str:
    return create_access_token(data={
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": user.tenant_id,
        "role": user.role,
        "full_name": user.full_name,
    })


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(request: TokenRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT token.

    Verifies credentials against users table. In dev mode, auto-creates
    the user on first login if they don't exist.
    """
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None and DEV_MODE:
        # Auto-create user in dev mode
        user = User(
            email=request.email,
            password_hash=pwd_context.hash(request.password),
            full_name=request.email.split("@")[0].replace(".", " ").title(),
            role="admin",
            tenant_id="default",
            is_active=True,
        )
        db.add(user)
        await db.flush()
        logger.info("Dev mode: auto-created user %s (id=%s)", request.email, user.id)

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    if not DEV_MODE and not pwd_context.verify(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conta desativada")

    token = _make_token(user)
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        email=user.email,
        tenant_id=user.tenant_id,
        role=user.role,
        full_name=user.full_name,
    )


@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user and create a tenant for the organization."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    # Create tenant
    try:
        tenant = create_tenant(
            name=request.organization,
            country_code="BR",
            primary_state=request.state_code,
            plan="free",
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Parâmetros de registro inválidos")

    user = User(
        email=request.email,
        password_hash=pwd_context.hash(request.password),
        full_name=request.name,
        role="admin",  # First user of a tenant is admin
        tenant_id=tenant.id,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    token = _make_token(user)
    logger.info("Registration: user=%s, tenant=%s", user.id, tenant.id)

    return RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        tenant_id=tenant.id,
        organization=request.organization,
        access_token=token,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: dict = Depends(require_auth), db: AsyncSession = Depends(get_db)):
    """Get current user profile from DB."""
    result = await db.execute(select(User).where(User.id == int(user["user_id"])))
    db_user = result.scalar_one_or_none()

    if db_user is None:
        # Fallback for JWT-only users (dev mode legacy)
        return UserProfileResponse(
            user_id=user.get("user_id", "unknown"),
            email=user.get("email", ""),
            full_name=user.get("full_name", user.get("email", "").split("@")[0]),
            tenant_id=user.get("tenant_id", "default"),
            role=user.get("role", "viewer"),
            anonymous=False,
        )

    tenant_dict = None
    tenant = get_tenant(db_user.tenant_id)
    if tenant is not None:
        tenant_dict = _tenant_to_dict(tenant)

    return UserProfileResponse(
        user_id=str(db_user.id),
        email=db_user.email,
        full_name=db_user.full_name,
        tenant_id=db_user.tenant_id,
        role=db_user.role,
        anonymous=False,
        is_active=db_user.is_active,
        preferences=db_user.preferences or {},
        tenant=tenant_dict,
    )


@router.put("/me", response_model=UserProfileResponse)
async def update_profile(
    body: UpdateProfileRequest,
    user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile."""
    result = await db.execute(select(User).where(User.id == int(user["user_id"])))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if body.full_name is not None:
        db_user.full_name = body.full_name
    if body.email is not None:
        db_user.email = body.email
    if body.preferences is not None:
        db_user.preferences = body.preferences

    await db.flush()

    return UserProfileResponse(
        user_id=str(db_user.id),
        email=db_user.email,
        full_name=db_user.full_name,
        tenant_id=db_user.tenant_id,
        role=db_user.role,
        anonymous=False,
        is_active=db_user.is_active,
        preferences=db_user.preferences or {},
    )


@router.put("/me/password")
async def change_password(
    body: ChangePasswordRequest,
    user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Change current user's password."""
    result = await db.execute(select(User).where(User.id == int(user["user_id"])))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if not pwd_context.verify(body.current_password, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    db_user.password_hash = pwd_context.hash(body.new_password)
    await db.flush()

    return {"message": "Senha alterada com sucesso"}
