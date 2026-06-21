"""Admin onboarding endpoints for locadoras, branches and users."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user, require_owner_or_admin
from api.services import job_service
from api.services.usage_stats import summarize_jobs
from src.auth.branches import User, hash_password
from src.auth.registry import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_OWNER,
    ROLE_VIEWER,
    create_branch,
    create_user,
    delete_branch,
    delete_user,
    public_locadora,
    update_branch,
    update_user_role,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ROLES = {ROLE_OWNER, ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER}


class BranchCreateRequest(BaseModel):
    branch_name: str = Field(min_length=1)
    inventory_name: Optional[str] = None


class BranchUpdateRequest(BaseModel):
    branch_name: str = Field(min_length=1)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3)
    name: str = Field(min_length=1)
    password: str = Field(min_length=6)
    role: str = ROLE_OPERATOR
    phone: str = ""


class UserRoleRequest(BaseModel):
    role: str


def _check_role(role: str) -> str:
    role = role.strip().lower()
    if role not in ROLES:
        raise HTTPException(status_code=400, detail="Papel invalido")
    return role


@router.get("/locadora")
async def get_my_locadora(user: User = Depends(require_owner_or_admin)):
    locadora = public_locadora(user.locadora_id)
    if locadora is None:
        raise HTTPException(status_code=404, detail="Locadora nao encontrada")
    return locadora


@router.get("/usage")
async def get_usage(user: User = Depends(require_owner_or_admin)):
    """Telemetria de piloto: agrega os jobs das unidades da locadora.

    Mede o uso por parceiro (volume, taxa de erro, tempo medio, revisoes)
    sem tabela nova — agrega a tabela `jobs` ja existente.
    """
    locadora = public_locadora(user.locadora_id)
    if locadora is None:
        raise HTTPException(status_code=404, detail="Locadora nao encontrada")
    jobs = []
    for b in locadora.get("branches", []):
        jobs.extend(job_service.list_jobs(branch_id=b["id"]))
    summary = summarize_jobs(jobs)
    ordered = sorted(
        jobs,
        key=lambda j: j.get("updated_at") or j.get("created_at"),
        reverse=True,
    )
    recent = [
        {
            "id": j["id"],
            "filename": j.get("filename"),
            "status": j.get("status"),
            "branch_id": j.get("branch_id"),
            "requires_review": bool(
                (j.get("results_data") or {}).get("requires_review")
            ),
            "updated_at": (
                j["updated_at"].isoformat()
                if hasattr(j.get("updated_at"), "isoformat")
                else j.get("updated_at")
            ),
        }
        for j in ordered[:15]
    ]
    return {"summary": summary, "recent": recent}


@router.post("/branches")
async def create_branch_endpoint(
    body: BranchCreateRequest,
    user: User = Depends(require_owner_or_admin),
):
    try:
        return create_branch(
            user.locadora_id,
            branch_name=body.branch_name,
            inventory_name=body.inventory_name,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Locadora nao encontrada") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/branches/{branch_id}")
async def update_branch_endpoint(
    branch_id: str,
    body: BranchUpdateRequest,
    user: User = Depends(require_owner_or_admin),
):
    try:
        updated = update_branch(user.locadora_id, branch_id, branch_name=body.branch_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if updated is None:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada")
    return updated


@router.delete("/branches/{branch_id}")
async def delete_branch_endpoint(
    branch_id: str,
    user: User = Depends(require_owner_or_admin),
):
    try:
        deleted = delete_branch(user.locadora_id, branch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not deleted:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada")
    return {"message": "Unidade removida", "id": branch_id}


@router.post("/users")
async def create_user_endpoint(
    body: UserCreateRequest,
    user: User = Depends(require_owner_or_admin),
):
    role = _check_role(body.role)
    try:
        return create_user(
            user.locadora_id,
            username=body.username,
            name=body.name,
            password_hash=hash_password(body.password),
            role=role,
            phone=body.phone,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Locadora nao encontrada") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/users/{username}/role")
async def update_user_role_endpoint(
    username: str,
    body: UserRoleRequest,
    user: User = Depends(require_owner_or_admin),
):
    role = _check_role(body.role)
    if username.strip().lower() == user.username and role not in {ROLE_OWNER, ROLE_ADMIN}:
        raise HTTPException(status_code=400, detail="Voce nao pode remover seu proprio papel admin")
    if not update_user_role(user.locadora_id, username, role):
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return {"username": username.strip().lower(), "role": role}


@router.delete("/users/{username}")
async def delete_user_endpoint(
    username: str,
    user: User = Depends(require_owner_or_admin),
):
    target = username.strip().lower()
    if target == user.username:
        raise HTTPException(status_code=400, detail="Voce nao pode remover seu proprio usuario")
    try:
        deleted = delete_user(user.locadora_id, target)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return {"message": "Usuario removido", "username": target}


@router.get("/roles")
async def list_roles(_: User = Depends(get_current_user)):
    return {
        "roles": [
            {"id": ROLE_OWNER, "label": "Owner"},
            {"id": ROLE_ADMIN, "label": "Admin"},
            {"id": ROLE_OPERATOR, "label": "Operator"},
            {"id": ROLE_VIEWER, "label": "Viewer"},
        ]
    }
