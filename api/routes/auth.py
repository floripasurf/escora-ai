"""Authentication endpoints: login / logout / whoami.

Login flow:
    POST /api/v1/auth/login  { username, password }
       → { token, user, locadora, branches: [...] }
    Engineer picks one of the returned branches client-side; the branch id
    is then sent on every subsequent request as `X-Branch-Id`, together with
    `Authorization: Bearer <token>`.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from src.auth.branches import (
    Branch,
    authenticate_user,
    change_password,
    create_session,
    get_locadora_of_user,
    resolve_session,
    revoke_session,
)
from api.deps import get_current_branch

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class BranchDTO(BaseModel):
    id: str
    branch_name: str
    inventory_name: str
    display_name: str


class LoginResponse(BaseModel):
    token: str
    username: str
    name: str
    locadora_id: str
    locadora_name: str
    branches: list[BranchDTO]


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    user = authenticate_user(body.username, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
        )
    locadora = get_locadora_of_user(user.username)
    if locadora is None or not locadora.branches:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem unidades disponíveis",
        )
    token = create_session(user)
    return LoginResponse(
        token=token,
        username=user.username,
        name=user.name,
        locadora_id=locadora.id,
        locadora_name=locadora.name,
        branches=[
            BranchDTO(
                id=b.id,
                branch_name=b.branch_name,
                inventory_name=b.inventory_name,
                display_name=b.display_name,
            )
            for b in locadora.branches
        ],
    )


@router.post("/change-password")
async def change_password_endpoint(
    body: ChangePasswordRequest,
    authorization: Optional[str] = Header(default=None),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sessão obrigatória")
    token = authorization.split(" ", 1)[1].strip()
    session = resolve_session(token)
    if session is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="A nova senha precisa ter ao menos 6 caracteres")
    ok = change_password(session["username"], body.old_password, body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    # Revoke current session so the user re-logs with the new password.
    revoke_session(token)
    return {"message": "Senha atualizada. Faça login novamente."}


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        revoke_session(token)
    return {"message": "ok"}


@router.get("/me")
async def me(
    authorization: Optional[str] = Header(default=None),
    x_branch_id: Optional[str] = Header(default=None, alias="X-Branch-Id"),
):
    """Return the current session owner and (optionally) selected branch.

    Unlike most endpoints, `/me` tolerates a missing X-Branch-Id so the UI can
    render the branch picker right after login.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sessão obrigatória")
    token = authorization.split(" ", 1)[1].strip()
    session = resolve_session(token)
    if session is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")

    locadora = None
    for loc_id_check, loc in _load_locadoras().items():
        if loc_id_check == session["locadora_id"]:
            locadora = loc
            break
    if locadora is None:
        raise HTTPException(status_code=404, detail="Locadora não encontrada")

    selected: Optional[Branch] = None
    if x_branch_id:
        for b in locadora.branches:
            if b.id == x_branch_id:
                selected = b
                break

    return {
        "username": session["username"],
        "locadora_id": locadora.id,
        "locadora_name": locadora.name,
        "branches": [
            {
                "id": b.id,
                "branch_name": b.branch_name,
                "inventory_name": b.inventory_name,
                "display_name": b.display_name,
            }
            for b in locadora.branches
        ],
        "selected_branch": {
            "id": selected.id,
            "branch_name": selected.branch_name,
            "inventory_name": selected.inventory_name,
            "display_name": selected.display_name,
        } if selected else None,
    }


def _load_locadoras():
    # Lazy import to avoid circulars; also picks up the env override at call time.
    from src.auth.branches import load_registry
    return load_registry()
