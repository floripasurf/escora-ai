"""Locadora / branch / user registry with password login and session tokens.

Data model:
    Locadora (employer / customer, e.g. "Orguel")
        ├── Branches (units, e.g. "Orguel São José dos Campos")
        │     → own inventory JSON, own learning store
        └── Users (engineer accounts that log in with username/password)
              → at login, the engineer picks which branch of their locadora
                they are currently working on. The chosen branch determines
                inventory and the learning partition used by the pipeline.

Storage: SQLite registry seeded from the legacy locadoras JSON on first use.

Passwords are stored with PBKDF2-HMAC-SHA256 (Python stdlib only — no new
dependency). Sessions are opaque tokens stored in a small SQLite database.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from src.auth import registry as registry_store

logger = logging.getLogger(__name__)

DEFAULT_LOCADORAS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "locadoras.json"
)

SESSION_TTL_SECONDS = 60 * 60 * 12  # 12 hours

# Session store: SQLite-backed so restarts don't log everybody out.
# Table created lazily on first use; path resolved from ESCORA_DATA_DIR.
_session_lock = threading.Lock()


def _sessions_db_path() -> Path:
    root = Path(os.environ.get("ESCORA_DATA_DIR", "./data"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "sessions.db"


_session_conn_cache: Optional[sqlite3.Connection] = None
_session_conn_cache_path: Optional[Path] = None


def _session_conn() -> sqlite3.Connection:
    global _session_conn_cache, _session_conn_cache_path
    path = _sessions_db_path()
    if _session_conn_cache is not None and _session_conn_cache_path == path:
        try:
            _session_conn_cache.execute("SELECT 1")
            return _session_conn_cache
        except Exception:
            _session_conn_cache = None
            _session_conn_cache_path = None
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _session_conn_cache = conn
    _session_conn_cache_path = path
    return conn


def init_sessions_db() -> None:
    with _session_lock, _session_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                locadora_id TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_exp ON sessions(expires_at)")


# ---------- Data classes ----------

@dataclass
class Branch:
    id: str
    branch_name: str
    inventory_name: str
    locadora_id: str = ""
    locadora_name: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.locadora_name} — {self.branch_name}".strip(" —")


@dataclass
class User:
    username: str
    name: str
    password_hash: str
    locadora_id: str
    role: str = registry_store.ROLE_OPERATOR


@dataclass
class Locadora:
    id: str
    name: str
    branches: List[Branch] = field(default_factory=list)
    users: List[User] = field(default_factory=list)


# ---------- Loader ----------

def _locadoras_path() -> Path:
    return registry_store.locadoras_json_path()


def load_registry() -> Dict[str, Locadora]:
    data = registry_store.registry_payload()
    out: Dict[str, Locadora] = {}
    for entry in data.get("locadoras", []):
        loc = Locadora(id=entry["id"], name=entry["name"])
        for b in entry.get("branches", []):
            loc.branches.append(Branch(
                id=b["id"],
                branch_name=b["branch_name"],
                inventory_name=b["inventory_name"],
                locadora_id=loc.id,
                locadora_name=loc.name,
            ))
        for u in entry.get("users", []):
            loc.users.append(User(
                username=u["username"],
                name=u.get("name", u["username"]),
                password_hash=u["password_hash"],
                locadora_id=loc.id,
                role=registry_store.normalize_role(u.get("role"), default=registry_store.ROLE_OWNER),
            ))
        out[loc.id] = loc
    return out


def get_branch(branch_id: str) -> Optional[Branch]:
    for loc in load_registry().values():
        for b in loc.branches:
            if b.id == branch_id:
                return b
    return None


def get_locadora_of_user(username: str) -> Optional[Locadora]:
    for loc in load_registry().values():
        for u in loc.users:
            if u.username == username:
                return loc
    return None


# ---------- Password hashing (stdlib only) ----------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"pbkdf2:sha256:100000${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, hex_hash = stored.split("$")
        if not algo.startswith("pbkdf2:sha256"):
            return False
        iters = int(algo.split(":")[-1])
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iters)
        return hmac.compare_digest(dk.hex(), hex_hash)
    except Exception:
        return False


# ---------- Login & session ----------

def authenticate_user(username: str, password: str) -> Optional[User]:
    for loc in load_registry().values():
        for u in loc.users:
            if u.username == username and verify_password(password, u.password_hash):
                return u
    return None


_session_create_counter = 0


def create_session(user: User) -> str:
    global _session_create_counter
    init_sessions_db()
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + SESSION_TTL_SECONDS
    with _session_lock, _session_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (token, username, locadora_id, expires_at) VALUES (?, ?, ?, ?)",
            (token, user.username, user.locadora_id, expires_at),
        )
    _session_create_counter += 1
    if _session_create_counter % 100 == 0:
        purge_expired_sessions()
    return token


def resolve_session(token: str) -> Optional[Dict]:
    if not token:
        return None
    init_sessions_db()
    with _session_lock, _session_conn() as conn:
        row = conn.execute(
            "SELECT username, locadora_id, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
    if row is None:
        return None
    username, locadora_id, expires_at = row
    if expires_at < time.time():
        revoke_session(token)
        return None
    return {"username": username, "locadora_id": locadora_id, "expires_at": expires_at}


def revoke_session(token: str) -> None:
    if not token:
        return
    try:
        with _session_lock, _session_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    except Exception as e:
        logger.warning(f"Failed to revoke session: {e}")


def purge_expired_sessions() -> int:
    """Remove all expired sessions. Returns count deleted."""
    try:
        init_sessions_db()
        now = time.time()
        with _session_lock, _session_conn() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            return cursor.rowcount
    except Exception:
        return 0


def clear_sessions() -> None:
    """Test helper: wipe all sessions."""
    try:
        init_sessions_db()
        init_reset_tokens_db()
        with _session_lock, _session_conn() as conn:
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM reset_tokens")
    except Exception:
        pass


# ---------- Password reset tokens ----------
# Mesmo padrão das sessões (SQLite em sessions.db), mas o token é armazenado
# como SHA-256: um vazamento do .db não permite resetar senhas de ninguém.

RESET_TOKEN_TTL_SECONDS = 60 * 60  # 1 hora


def init_reset_tokens_db() -> None:
    with _session_lock, _session_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reset_tokens (
                token_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            )
            """
        )


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(username: str) -> str:
    """Cria um token de reset single-use (TTL 1h) e retorna o valor CRU."""
    init_sessions_db()
    init_reset_tokens_db()
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + RESET_TOKEN_TTL_SECONDS
    with _session_lock, _session_conn() as conn:
        # Invalida tokens anteriores do mesmo usuário (só o mais novo vale).
        conn.execute(
            "UPDATE reset_tokens SET used = 1 WHERE username = ?",
            (username.strip().lower(),),
        )
        conn.execute(
            "INSERT INTO reset_tokens (token_hash, username, expires_at) VALUES (?, ?, ?)",
            (_hash_reset_token(token), username.strip().lower(), expires_at),
        )
    return token


def consume_reset_token(token: str) -> Optional[str]:
    """Valida TTL + single-use e marca como usado. Retorna o username ou None."""
    if not token:
        return None
    init_reset_tokens_db()
    with _session_lock, _session_conn() as conn:
        row = conn.execute(
            "SELECT username, expires_at, used FROM reset_tokens WHERE token_hash = ?",
            (_hash_reset_token(token),),
        ).fetchone()
        if row is None:
            return None
        username, expires_at, used = row
        if used or expires_at < time.time():
            return None
        conn.execute(
            "UPDATE reset_tokens SET used = 1 WHERE token_hash = ?",
            (_hash_reset_token(token),),
        )
    return username


def revoke_sessions_for_user(username: str) -> int:
    """Derruba todas as sessões do usuário (pós-reset de senha)."""
    init_sessions_db()
    with _session_lock, _session_conn() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE username = ?",
            (username.strip().lower(),),
        )
        return cur.rowcount


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_create_user_lock = threading.Lock()


def create_user(
    name: str,
    email: str,
    company: str,
    phone: str,
    password: str,
    branch_name: str = "Sede",
    inventory_name: str = "",
) -> Optional[User]:
    """Register a new user with their own locadora + default branch.

    Returns the User on success, None if the email is already taken.
    Persists to the SQLite registry seeded from the legacy locadoras JSON.
    """
    if not password or len(password) < 6:
        return None
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return None

    with _create_user_lock:
        created = registry_store.create_locadora_with_owner(
            name=company or name,
            owner_name=name,
            owner_email=email,
            owner_phone=phone,
            password_hash=hash_password(password),
            branch_name=branch_name or "Sede",
            inventory_name=inventory_name or None,
        )
        if created is None:
            return None

    return User(
        username=email,
        name=name,
        password_hash="",
        locadora_id=created["locadora_id"],
        role=registry_store.ROLE_OWNER,
    )


def repair_default_inventory_names() -> int:
    """Replace shared 'default' inventory names with per-branch names.

    Older signups used inventory_name="default", which can make unrelated
    locadoras share the same stock file. This migration is intentionally small
    so current deployments can repair themselves at startup.
    """
    changed = registry_store.repair_default_inventory_names()
    if not changed:
        return 0
    for loc in load_registry().values():
        for branch in loc.branches:
            if branch.inventory_name == branch.id:
                _copy_default_inventory_if_needed(branch.id)
    logger.info(f"Repaired {changed} shared default inventory name(s)")
    return changed


def _copy_default_inventory_if_needed(new_name: str) -> None:
    try:
        from src.engine.inventory import DEFAULT_INVENTORY_DIR, inventory_path

        dest = inventory_path(new_name)
        if dest.exists():
            return
        source = inventory_path("default")
        if not source.exists():
            fallback = DEFAULT_INVENTORY_DIR / "default.json"
            source = fallback if fallback.exists() else source
        if not source.exists():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    except Exception as e:
        logger.warning(f"Failed to copy default inventory to {new_name}: {e}")


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """Verify old password and replace it in the SQLite registry.

    Returns True on success, False if the old password didn't match or the
    user isn't in the registry.
    """
    if not new_password or len(new_password) < 6:
        return False
    user = authenticate_user(username, old_password)
    if user is None:
        return False
    return registry_store.update_password(username, hash_password(new_password))
