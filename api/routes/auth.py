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
    create_user,
    get_locadora_of_user,
    resolve_session,
    revoke_session,
)
from src.models.methodology import load_methodology
from api.deps import get_current_branch
from api.services.methodology_view import serialize_profile

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _branch_dto(b: Branch, locadora_id: str) -> "BranchDTO":
    """Monta o BranchDTO com a metodologia resolvida da locadora/branch.

    A metodologia e um atributo da locadora (§28.9): load_methodology faz o
    merge locadora -> branch e cai nos defaults em codigo na ausencia do campo.
    """
    return BranchDTO(
        id=b.id,
        branch_name=b.branch_name,
        inventory_name=b.inventory_name,
        display_name=b.display_name,
        metodologia=serialize_profile(
            load_methodology(branch_id=b.id, locadora_id=locadora_id)
        ),
    )


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    name: str
    email: str
    company: str = ""
    phone: str = ""
    password: str
    branch_name: str = "Sede"
    inventory_name: str = ""


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class BranchDTO(BaseModel):
    id: str
    branch_name: str
    inventory_name: str
    display_name: str
    metodologia: Optional[dict] = None


class LoginResponse(BaseModel):
    token: str
    username: str
    name: str
    role: str
    locadora_id: str
    locadora_name: str
    branches: list[BranchDTO]


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    user = authenticate_user(body.username.strip().lower(), body.password)
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
        role=user.role,
        locadora_id=locadora.id,
        locadora_name=locadora.name,
        branches=[_branch_dto(b, locadora.id) for b in locadora.branches],
    )


@router.post("/signup")
async def signup(body: SignupRequest):
    if not body.name or not body.email or not body.password:
        raise HTTPException(status_code=400, detail="Nome, email e senha são obrigatórios")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="A senha precisa ter ao menos 6 caracteres")
    import re
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", body.email.strip()):
        raise HTTPException(status_code=400, detail="Email inválido")
    try:
        user = create_user(
            name=body.name,
            email=body.email,
            company=body.company,
            phone=body.phone,
            password=body.password,
            branch_name=body.branch_name,
            inventory_name=body.inventory_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if user is None:
        raise HTTPException(status_code=409, detail="Este email já está cadastrado")
    # Auto-login after signup
    token = create_session(user)
    locadora = get_locadora_of_user(user.username)
    return LoginResponse(
        token=token,
        username=user.username,
        name=user.name,
        role=user.role,
        locadora_id=locadora.id if locadora else user.locadora_id,
        locadora_name=locadora.name if locadora else body.company,
        branches=[
            _branch_dto(b, locadora.id)
            for b in (locadora.branches if locadora else [])
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
    current_user = next((u for u in locadora.users if u.username == session["username"]), None)
    if x_branch_id:
        for b in locadora.branches:
            if b.id == x_branch_id:
                selected = b
                break

    def _branch_payload(b: Branch) -> dict:
        return {
            "id": b.id,
            "branch_name": b.branch_name,
            "inventory_name": b.inventory_name,
            "display_name": b.display_name,
            "metodologia": serialize_profile(
                load_methodology(branch_id=b.id, locadora_id=locadora.id)
            ),
        }

    return {
        "username": session["username"],
        "name": current_user.name if current_user else session["username"],
        "role": current_user.role if current_user else "operator",
        "locadora_id": locadora.id,
        "locadora_name": locadora.name,
        "branches": [_branch_payload(b) for b in locadora.branches],
        "selected_branch": _branch_payload(selected) if selected else None,
    }


def _load_locadoras():
    # Lazy import to avoid circulars; also picks up the env override at call time.
    from src.auth.branches import load_registry
    return load_registry()
