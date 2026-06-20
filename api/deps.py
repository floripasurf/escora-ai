"""FastAPI dependencies: session-token auth + branch resolution.

The engineer logs in with username/password (→ `create_session`) and then sends
every subsequent request with two headers:

    Authorization: Bearer <session_token>
    X-Branch-Id:   <branch_id>

`get_current_branch` validates the session, confirms that the branch belongs
to the session owner's locadora, and returns the `Branch` object.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from src.auth.branches import (
    Branch,
    User,
    get_branch,
    get_locadora_of_user,
    resolve_session,
)
from src.auth.registry import ROLE_ADMIN, ROLE_OPERATOR, ROLE_OWNER


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sessão obrigatório (Authorization: Bearer ...)",
        )
    return authorization.split(" ", 1)[1].strip()


def _resolve_required_session(authorization: Optional[str]) -> dict:
    token = _extract_bearer(authorization)
    session = resolve_session(token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada",
        )
    return session


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> User:
    session = _resolve_required_session(authorization)
    locadora = get_locadora_of_user(session["username"])
    if locadora is None or locadora.id != session["locadora_id"]:
        raise HTTPException(status_code=404, detail="Locadora não encontrada")
    for user in locadora.users:
        if user.username == session["username"]:
            return user
    raise HTTPException(status_code=404, detail="Usuário não encontrado")


def require_roles(*roles: str):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente",
            )
        return user

    return _dep


require_owner_or_admin = require_roles(ROLE_OWNER, ROLE_ADMIN)
require_operator_or_admin = require_roles(ROLE_OWNER, ROLE_ADMIN, ROLE_OPERATOR)


async def get_current_branch(
    authorization: Optional[str] = Header(default=None),
    x_branch_id: Optional[str] = Header(default=None, alias="X-Branch-Id"),
) -> Branch:
    session = _resolve_required_session(authorization)

    if not x_branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecione uma unidade (X-Branch-Id)",
        )

    branch = get_branch(x_branch_id)
    if branch is None or branch.locadora_id != session["locadora_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unidade não pertence à sua locadora",
        )
    return branch
