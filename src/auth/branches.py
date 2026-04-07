"""Locadora / branch / user registry with password login and session tokens.

Data model:
    Locadora (employer / customer, e.g. "Supplier")
        ├── Branches (units, e.g. "Supplier São José dos Campos")
        │     → own inventory JSON, own learning store
        └── Users (engineer accounts that log in with username/password)
              → at login, the engineer picks which branch of their locadora
                they are currently working on. The chosen branch determines
                inventory and the learning partition used by the pipeline.

Storage: a single JSON file (default: data/locadoras.json). Human-editable;
swap for a real DB later without touching the rest of the codebase.

Passwords are stored with PBKDF2-HMAC-SHA256 (Python stdlib only — no new
dependency). Sessions are opaque tokens kept in process memory for MVP.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

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


def _session_conn() -> sqlite3.Connection:
    path = _sessions_db_path()
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
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


@dataclass
class Locadora:
    id: str
    name: str
    branches: List[Branch] = field(default_factory=list)
    users: List[User] = field(default_factory=list)


# ---------- Loader ----------

def _locadoras_path() -> Path:
    override = os.environ.get("ESCORA_LOCADORAS_FILE")
    return Path(override) if override else DEFAULT_LOCADORAS_PATH


def load_registry() -> Dict[str, Locadora]:
    path = _locadoras_path()
    if not path.exists():
        logger.warning(f"Locadoras file not found: {path}")
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
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


def create_session(user: User) -> str:
    init_sessions_db()
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + SESSION_TTL_SECONDS
    with _session_lock, _session_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sessions (token, username, locadora_id, expires_at) VALUES (?, ?, ?, ?)",
            (token, user.username, user.locadora_id, expires_at),
        )
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


def clear_sessions() -> None:
    """Test helper: wipe all sessions."""
    try:
        init_sessions_db()
        with _session_lock, _session_conn() as conn:
            conn.execute("DELETE FROM sessions")
    except Exception:
        pass


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """Verify old password and replace it in the locadoras JSON on disk.

    Returns True on success, False if the old password didn't match or the
    user isn't in the registry. Writes to whatever path `_locadoras_path()`
    resolves to (respecting `ESCORA_LOCADORAS_FILE`).
    """
    if not new_password or len(new_password) < 6:
        return False
    path = _locadoras_path()
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    updated = False
    for entry in data.get("locadoras", []):
        for u in entry.get("users", []):
            if u["username"] == username and verify_password(old_password, u["password_hash"]):
                u["password_hash"] = hash_password(new_password)
                updated = True
                break
        if updated:
            break
    if not updated:
        return False
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True
