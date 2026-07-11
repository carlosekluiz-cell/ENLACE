"""
Propagation projects — saved link/coverage studies per user.

A project is a named JSON snapshot of planner state (mode, points,
parameters, and optionally cached results). Table is created lazily
(same pattern as calibration/tenants).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from python.api.auth.dependencies import require_auth
from python.api.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

_table_ensured = False


def _conn():
    return psycopg2.connect(Settings().database_sync_url)


def _ensure_table():
    global _table_ensured
    if _table_ensured:
        return
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rf_projects (
                id BIGSERIAL PRIMARY KEY,
                user_id VARCHAR(64) NOT NULL,
                tenant_id VARCHAR(100) NOT NULL DEFAULT 'default',
                name VARCHAR(200) NOT NULL,
                kind VARCHAR(20) NOT NULL,           -- 'enlace' | 'cobertura'
                state JSONB NOT NULL,                -- planner snapshot
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_rfp_user ON rf_projects (user_id, updated_at DESC)"
        )
        conn.commit()
        cur.close()
        _table_ensured = True
    finally:
        conn.close()


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(enlace|cobertura)$")
    state: dict[str, Any]


class ProjectPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    state: Optional[dict[str, Any]] = None


def _uid(user: dict) -> str:
    return str(user.get("user_id", "anonymous"))


@router.get("")
async def list_projects(user: dict = Depends(require_auth)):
    _ensure_table()
    conn = _conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT id, name, kind, created_at, updated_at
               FROM rf_projects WHERE user_id = %s
               ORDER BY updated_at DESC LIMIT 200""",
            (_uid(user),),
        )
        return {"projects": [dict(r) for r in cur.fetchall()]}
    finally:
        conn.close()


@router.post("")
async def create_project(body: ProjectIn, user: dict = Depends(require_auth)):
    _ensure_table()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO rf_projects (user_id, tenant_id, name, kind, state)
               VALUES (%s, %s, %s, %s, %s::jsonb) RETURNING id""",
            (
                _uid(user),
                str(user.get("tenant_id", "default")),
                body.name,
                body.kind,
                json.dumps(body.state),
            ),
        )
        pid = cur.fetchone()[0]
        conn.commit()
        return {"id": pid, "name": body.name}
    finally:
        conn.close()


@router.get("/{project_id}")
async def get_project(project_id: int, user: dict = Depends(require_auth)):
    _ensure_table()
    conn = _conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM rf_projects WHERE id = %s AND user_id = %s",
            (project_id, _uid(user)),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        return dict(row)
    finally:
        conn.close()


@router.patch("/{project_id}")
async def update_project(
    project_id: int, body: ProjectPatch, user: dict = Depends(require_auth)
):
    _ensure_table()
    if body.name is None and body.state is None:
        raise HTTPException(status_code=400, detail="nada para atualizar")
    conn = _conn()
    try:
        cur = conn.cursor()
        sets, args = [], []
        if body.name is not None:
            sets.append("name = %s")
            args.append(body.name)
        if body.state is not None:
            sets.append("state = %s::jsonb")
            args.append(json.dumps(body.state))
        sets.append("updated_at = NOW()")
        args += [project_id, _uid(user)]
        cur.execute(
            f"UPDATE rf_projects SET {', '.join(sets)} WHERE id = %s AND user_id = %s",
            args,
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        conn.commit()
        return {"updated": True}
    finally:
        conn.close()


@router.delete("/{project_id}")
async def delete_project(project_id: int, user: dict = Depends(require_auth)):
    _ensure_table()
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM rf_projects WHERE id = %s AND user_id = %s",
            (project_id, _uid(user)),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        conn.commit()
        return {"deleted": True}
    finally:
        conn.close()
