"""
ENLACE Admin Router

Admin-only endpoints for user management, tenant listing, and pipeline monitoring.
All endpoints require admin role.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from passlib.context import CryptContext

from python.api.auth.dependencies import require_admin
from python.api.database import get_db
from python.api.models.orm import User, PipelineRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    tenant_id: str
    is_active: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=1)
    role: str = Field("viewer", pattern="^(admin|manager|analyst|viewer)$")
    tenant_id: str = Field("default")


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|manager|analyst|viewer)$")
    is_active: Optional[bool] = None


class PipelineOut(BaseModel):
    id: int
    pipeline_name: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str
    rows_processed: Optional[int] = None
    rows_inserted: Optional[int] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserOut])
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    role: Optional[str] = None,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users with pagination and filtering."""
    q = select(User).order_by(User.id)

    if search:
        q = q.where(User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%"))
    if role:
        q = q.where(User.role == role)

    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    users = result.scalars().all()

    return [
        UserOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            tenant_id=u.tenant_id,
            is_active=u.is_active,
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: CreateUserRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin only)."""
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    user = User(
        email=body.email,
        password_hash=pwd_context.hash(body.password),
        full_name=body.full_name,
        role=body.role,
        tenant_id=body.tenant_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role or active status."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.flush()

    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: int,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a user (soft delete)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    user.is_active = False
    await db.flush()

    return {"message": f"Usuário {user.email} desativado"}


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

@router.get("/pipelines", response_model=list[PipelineOut])
async def list_pipelines(
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List pipeline runs with status and timing."""
    q = select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit)
    if status_filter:
        q = q.where(PipelineRun.status == status_filter)

    result = await db.execute(q)
    runs = result.scalars().all()

    return [
        PipelineOut(
            id=r.id,
            pipeline_name=r.pipeline_name,
            started_at=r.started_at.isoformat() if r.started_at else None,
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            status=r.status,
            rows_processed=r.rows_processed,
            rows_inserted=r.rows_inserted,
            error_message=r.error_message,
        )
        for r in runs
    ]


@router.post("/pipelines/{name}/run")
async def trigger_pipeline(
    name: str,
    admin: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a pipeline re-run (creates a pending pipeline_run record)."""
    from datetime import datetime, timezone

    run = PipelineRun(
        pipeline_name=name,
        started_at=datetime.now(timezone.utc),
        status="pending",
    )
    db.add(run)
    await db.flush()

    return {"message": f"Pipeline '{name}' enfileirado", "run_id": run.id}
