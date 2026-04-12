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


_session_conn_cache: Optional[sqlite3.Connection] = None


def _session_conn() -> sqlite3.Connection:
    global _session_conn_cache
    if _session_conn_cache is not None:
        try:
            _session_conn_cache.execute("SELECT 1")
            return _session_conn_cache
        except Exception:
            _session_conn_cache = None
    path = _sessions_db_path()
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _session_conn_cache = conn
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
        with _session_lock, _session_conn() as conn:
            conn.execute("DELETE FROM sessions")
    except Exception:
        pass


import re
import fcntl

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_create_user_lock = threading.Lock()


def create_user(
    name: str,
    email: str,
    company: str,
    phone: str,
    password: str,
) -> Optional[User]:
    """Register a new user with their own locadora + default branch.

    Returns the User on success, None if the email is already taken.
    Writes to the same locadoras JSON file used by the rest of the system.
    Thread-safe: uses both a threading lock and file-level locking.
    """
    if not password or len(password) < 6:
        return None
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return None

    with _create_user_lock:
        path = _locadoras_path()
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {"version": 1, "locadoras": []}
        else:
            data = json.loads(path.read_text(encoding="utf-8"))

        # Check uniqueness (email = username)
        for entry in data.get("locadoras", []):
            for u in entry.get("users", []):
                if u["username"] == email:
                    return None

        # Slugify for IDs
        slug = re.sub(r"[^a-z0-9-]", "-", email.split("@")[0].lower())
        loc_id = f"loc-{slug}"
        branch_id = f"{loc_id}-default"

        new_locadora = {
            "id": loc_id,
            "name": company or name,
            "branches": [
                {
                    "id": branch_id,
                    "branch_name": "Sede",
                    "inventory_name": "default",
                }
            ],
            "users": [
                {
                    "username": email,
                    "name": name,
                    "password_hash": hash_password(password),
                    "phone": phone,
                }
            ],
        }
        data["locadoras"].append(new_locadora)

        # Atomic write with file lock to prevent race conditions
        tmp_path = path.with_suffix(".tmp")
        content = json.dumps(data, indent=2, ensure_ascii=False)
        with open(tmp_path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(path)

    return User(
        username=email,
        name=name,
        password_hash="",
        locadora_id=loc_id,
    )


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
