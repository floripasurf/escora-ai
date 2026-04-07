"""FastAPI dependencies: session-token auth + branch resolution.

The engineer logs in with username/password (→ `create_session`) and then sends
every subsequent request with two headers:

    Authorization: Bearer <session_token>
    X-Branch-Id:   <branch_id>

`get_current_branch` validates the session, confirms that the branch belongs
to the session owner's locadora, and returns the `Branch` object.
"""

from typing import Optional

from fastapi import Header, HTTPException, status

from src.auth.branches import (
    Branch,
    get_branch,
    get_locadora_of_user,
    resolve_session,
)


async def get_current_branch(
    authorization: Optional[str] = Header(default=None),
    x_branch_id: Optional[str] = Header(default=None, alias="X-Branch-Id"),
) -> Branch:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sessão obrigatório (Authorization: Bearer ...)",
        )
    token = authorization.split(" ", 1)[1].strip()
    session = resolve_session(token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada",
        )

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
