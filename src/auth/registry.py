"""SQLite-backed locadora/branch/user registry.

This module is the durable onboarding registry. It seeds itself from the
legacy ``locadoras.json`` only when the SQLite database is empty, then becomes
the source of truth for authentication, branch selection and admin screens.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_LOCADORAS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "locadoras.json"
)

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
VALID_ROLES = {ROLE_OWNER, ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER}
LEGACY_ROLE_MAP = {
    "engineer": ROLE_OPERATOR,
    "engenheiro": ROLE_OPERATOR,
}

_lock = threading.Lock()
_conn_cache: Optional[sqlite3.Connection] = None
_conn_cache_path: Optional[Path] = None


def locadoras_json_path() -> Path:
    override = os.environ.get("ESCORA_LOCADORAS_FILE")
    return Path(override) if override else DEFAULT_LOCADORAS_PATH


def registry_db_path() -> Path:
    override = os.environ.get("ESCORA_REGISTRY_DB")
    if override:
        return Path(override)
    root = Path(os.environ.get("ESCORA_DATA_DIR", "./data"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "registry.db"


def _connect() -> sqlite3.Connection:
    global _conn_cache, _conn_cache_path
    path = registry_db_path()
    if _conn_cache is not None and _conn_cache_path == path:
        try:
            _conn_cache.execute("SELECT 1")
            return _conn_cache
        except Exception:
            _conn_cache = None
            _conn_cache_path = None
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _conn_cache = conn
    _conn_cache_path = path
    return conn


def normalize_role(role: Optional[str], default: str = ROLE_OPERATOR) -> str:
    value = (role or default).strip().lower()
    value = LEGACY_ROLE_MAP.get(value, value)
    return value if value in VALID_ROLES else default


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _json_loads(value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "item"


def _inventory_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_.-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "inventory"


def _unique_id(conn: sqlite3.Connection, table: str, base: str) -> str:
    candidate = base
    n = 2
    while conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (candidate,)).fetchone():
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def init_registry_db() -> None:
    with _lock:
        conn = _connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS locadoras (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS branches (
                id TEXT PRIMARY KEY,
                locadora_id TEXT NOT NULL REFERENCES locadoras(id) ON DELETE CASCADE,
                branch_name TEXT NOT NULL,
                inventory_name TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                locadora_id TEXT NOT NULL REFERENCES locadoras(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_branches_locadora ON branches(locadora_id);
            CREATE INDEX IF NOT EXISTS idx_users_locadora ON users(locadora_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_branches_inventory_name ON branches(inventory_name);
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM locadoras").fetchone()[0]
        if count == 0:
            _seed_from_json(conn, locadoras_json_path())


def _seed_from_json(conn: sqlite3.Connection, path: Path) -> None:
    if not path.exists():
        logger.info(f"Registry seed skipped; locadoras JSON not found: {path}")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Registry seed failed reading {path}: {exc}")
        return
    now = time.time()
    seeded = 0
    for entry in data.get("locadoras", []) or []:
        loc_id = str(entry.get("id") or "").strip()
        name = str(entry.get("name") or loc_id).strip()
        if not loc_id or not name:
            continue
        metadata = {}
        if isinstance(entry.get("metodologia"), dict):
            metadata["metodologia"] = entry["metodologia"]
        conn.execute(
            "INSERT OR IGNORE INTO locadoras (id, name, metadata_json, created_at) VALUES (?, ?, ?, ?)",
            (loc_id, name, _json_dumps(metadata), now),
        )
        for branch in entry.get("branches", []) or []:
            branch_id = str(branch.get("id") or "").strip()
            branch_name = str(branch.get("branch_name") or branch_id).strip()
            inventory_name = str(branch.get("inventory_name") or branch_id).strip()
            if inventory_name == "default":
                inventory_name = branch_id
            if not branch_id:
                continue
            b_meta = {}
            if isinstance(branch.get("metodologia"), dict):
                b_meta["metodologia"] = branch["metodologia"]
            conn.execute(
                """
                INSERT OR IGNORE INTO branches
                    (id, locadora_id, branch_name, inventory_name, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (branch_id, loc_id, branch_name, inventory_name, _json_dumps(b_meta), now),
            )
        for user in entry.get("users", []) or []:
            username = str(user.get("username") or "").strip().lower()
            password_hash = str(user.get("password_hash") or "")
            if not username or not password_hash:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO users
                    (username, locadora_id, name, password_hash, role, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    loc_id,
                    str(user.get("name") or username),
                    password_hash,
                    normalize_role(user.get("role"), default=ROLE_OWNER),
                    str(user.get("phone") or ""),
                    now,
                ),
            )
        seeded += 1
    if seeded:
        logger.info(f"Seeded SQLite registry from {path}: {seeded} locadora(s)")


def registry_payload() -> Dict[str, Any]:
    init_registry_db()
    conn = _connect()
    loc_rows = conn.execute("SELECT * FROM locadoras ORDER BY name, id").fetchall()
    locadoras = []
    for loc in loc_rows:
        loc_dict = {
            "id": loc["id"],
            "name": loc["name"],
            "branches": [],
            "users": [],
        }
        loc_meta = _json_loads(loc["metadata_json"])
        if isinstance(loc_meta.get("metodologia"), dict):
            loc_dict["metodologia"] = loc_meta["metodologia"]
        for branch in conn.execute(
            "SELECT * FROM branches WHERE locadora_id = ? ORDER BY branch_name, id",
            (loc["id"],),
        ).fetchall():
            b_dict = {
                "id": branch["id"],
                "branch_name": branch["branch_name"],
                "inventory_name": branch["inventory_name"],
            }
            b_meta = _json_loads(branch["metadata_json"])
            if isinstance(b_meta.get("metodologia"), dict):
                b_dict["metodologia"] = b_meta["metodologia"]
            loc_dict["branches"].append(b_dict)
        for user in conn.execute(
            "SELECT username, name, password_hash, role, phone FROM users WHERE locadora_id = ? ORDER BY name, username",
            (loc["id"],),
        ).fetchall():
            loc_dict["users"].append(
                {
                    "username": user["username"],
                    "name": user["name"],
                    "password_hash": user["password_hash"],
                    "role": normalize_role(user["role"]),
                    "phone": user["phone"],
                }
            )
        locadoras.append(loc_dict)
    return {"version": 2, "locadoras": locadoras}


def public_locadora(locadora_id: str) -> Optional[Dict[str, Any]]:
    payload = registry_payload()
    for loc in payload["locadoras"]:
        if loc["id"] == locadora_id:
            return {
                "id": loc["id"],
                "name": loc["name"],
                "branches": loc.get("branches", []),
                "users": [
                    {
                        "username": u["username"],
                        "name": u["name"],
                        "role": normalize_role(u.get("role")),
                        "phone": u.get("phone", ""),
                    }
                    for u in loc.get("users", [])
                ],
            }
    return None


def methodology_metadata(locadora_id: Optional[str], branch_id: Optional[str]) -> Dict[str, Any]:
    payload = registry_payload()
    for loc in payload.get("locadoras", []):
        if locadora_id and loc.get("id") != locadora_id:
            continue
        branch = None
        if branch_id:
            branch = next((b for b in loc.get("branches", []) if b.get("id") == branch_id), None)
        if branch_id and branch is None:
            continue
        merged: Dict[str, Any] = {}
        if isinstance(loc.get("metodologia"), dict):
            merged.update(loc["metodologia"])
        if branch and isinstance(branch.get("metodologia"), dict):
            merged.update(branch["metodologia"])
        return merged
    return {}


def locadora_quota_jobs_mes(locadora_id: Optional[str]) -> int:
    """Quota mensal de jobs da locadora (0 = ilimitado).

    Fonte: metadata_json["quota_jobs_mes"] da locadora; fallback no env
    ESCORA_DEFAULT_MONTHLY_QUOTA (tambem 0 = ilimitado por default).
    """
    default = 0
    try:
        default = int(os.environ.get("ESCORA_DEFAULT_MONTHLY_QUOTA", "0"))
    except ValueError:
        default = 0
    if not locadora_id:
        return default
    init_registry_db()
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT metadata_json FROM locadoras WHERE id = ?", (locadora_id,)
        ).fetchone()
    if row is None:
        return default
    meta = _json_loads(row["metadata_json"])
    quota = meta.get("quota_jobs_mes")
    if isinstance(quota, int) and quota >= 0:
        return quota
    return default


def create_locadora_with_owner(
    *,
    name: str,
    owner_name: str,
    owner_email: str,
    owner_phone: str,
    password_hash: str,
    branch_name: str = "Sede",
    inventory_name: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    init_registry_db()
    email = owner_email.strip().lower()
    if not email or not password_hash:
        return None
    with _lock:
        conn = _connect()
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (email,)).fetchone():
            return None
        loc_base = f"loc-{_slug(email.split('@')[0])}"
        loc_id = _unique_id(conn, "locadoras", loc_base)
        first_branch_name = (branch_name or "Sede").strip() or "Sede"
        branch_id = _unique_id(conn, "branches", f"{loc_id}-{_slug(first_branch_name)}")
        inventory = _inventory_slug(inventory_name) if inventory_name else branch_id
        if conn.execute("SELECT 1 FROM branches WHERE inventory_name = ?", (inventory,)).fetchone():
            raise ValueError("Nome de inventario ja cadastrado")
        loc_name = (name or owner_name or email).strip()
        now = time.time()
        conn.execute(
            "INSERT INTO locadoras (id, name, metadata_json, created_at) VALUES (?, ?, ?, ?)",
            (loc_id, loc_name, _json_dumps({}), now),
        )
        conn.execute(
            """
            INSERT INTO branches (id, locadora_id, branch_name, inventory_name, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (branch_id, loc_id, first_branch_name, inventory, _json_dumps({}), now),
        )
        conn.execute(
            """
            INSERT INTO users (username, locadora_id, name, password_hash, role, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (email, loc_id, owner_name or email, password_hash, ROLE_OWNER, owner_phone or "", now),
        )
    return {
        "locadora_id": loc_id,
        "branch_id": branch_id,
        "inventory_name": inventory,
        "username": email,
    }


def create_branch(locadora_id: str, branch_name: str, inventory_name: Optional[str] = None) -> Dict[str, str]:
    init_registry_db()
    name = branch_name.strip()
    if not name:
        raise ValueError("Nome da unidade e obrigatorio")
    with _lock:
        conn = _connect()
        loc = conn.execute("SELECT id FROM locadoras WHERE id = ?", (locadora_id,)).fetchone()
        if loc is None:
            raise KeyError(locadora_id)
        branch_id = _unique_id(conn, "branches", f"{locadora_id}-{_slug(name)}")
        inv = _inventory_slug(inventory_name) if inventory_name else branch_id
        if conn.execute("SELECT 1 FROM branches WHERE inventory_name = ?", (inv,)).fetchone():
            raise ValueError("Nome de inventario ja cadastrado")
        now = time.time()
        conn.execute(
            """
            INSERT INTO branches (id, locadora_id, branch_name, inventory_name, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (branch_id, locadora_id, name, inv, _json_dumps({}), now),
        )
    return {"id": branch_id, "branch_name": name, "inventory_name": inv}


def update_branch(locadora_id: str, branch_id: str, branch_name: str) -> Optional[Dict[str, str]]:
    init_registry_db()
    name = branch_name.strip()
    if not name:
        raise ValueError("Nome da unidade e obrigatorio")
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT id, inventory_name FROM branches WHERE locadora_id = ? AND id = ?",
            (locadora_id, branch_id.strip()),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE branches SET branch_name = ? WHERE locadora_id = ? AND id = ?",
            (name, locadora_id, branch_id.strip()),
        )
    return {"id": branch_id.strip(), "branch_name": name, "inventory_name": row["inventory_name"]}


def delete_branch(locadora_id: str, branch_id: str) -> bool:
    init_registry_db()
    branch = branch_id.strip()
    with _lock:
        conn = _connect()
        count = conn.execute(
            "SELECT COUNT(*) FROM branches WHERE locadora_id = ?",
            (locadora_id,),
        ).fetchone()[0]
        if count <= 1:
            raise ValueError("Nao e possivel remover a ultima unidade")
        cur = conn.execute(
            "DELETE FROM branches WHERE locadora_id = ? AND id = ?",
            (locadora_id, branch),
        )
        return cur.rowcount > 0


def create_user(
    locadora_id: str,
    *,
    username: str,
    name: str,
    password_hash: str,
    role: str = ROLE_OPERATOR,
    phone: str = "",
) -> Dict[str, str]:
    init_registry_db()
    user = username.strip().lower()
    if not user or not password_hash:
        raise ValueError("Usuario e senha sao obrigatorios")
    role_norm = normalize_role(role)
    with _lock:
        conn = _connect()
        if conn.execute("SELECT 1 FROM locadoras WHERE id = ?", (locadora_id,)).fetchone() is None:
            raise KeyError(locadora_id)
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (user,)).fetchone():
            raise ValueError("Usuario ja cadastrado")
        conn.execute(
            """
            INSERT INTO users (username, locadora_id, name, password_hash, role, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user, locadora_id, name or user, password_hash, role_norm, phone or "", time.time()),
        )
    return {"username": user, "name": name or user, "role": role_norm, "phone": phone or ""}


def delete_user(locadora_id: str, username: str) -> bool:
    init_registry_db()
    user = username.strip().lower()
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT role FROM users WHERE locadora_id = ? AND username = ?",
            (locadora_id, user),
        ).fetchone()
        if row is None:
            return False
        if normalize_role(row["role"]) == ROLE_OWNER:
            owners = conn.execute(
                "SELECT COUNT(*) FROM users WHERE locadora_id = ? AND role = ?",
                (locadora_id, ROLE_OWNER),
            ).fetchone()[0]
            if owners <= 1:
                raise ValueError("Nao e possivel remover o ultimo owner")
        cur = conn.execute(
            "DELETE FROM users WHERE locadora_id = ? AND username = ?",
            (locadora_id, user),
        )
        return cur.rowcount > 0


def update_user_role(locadora_id: str, username: str, role: str) -> bool:
    init_registry_db()
    role_norm = normalize_role(role)
    with _lock, _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET role = ? WHERE locadora_id = ? AND username = ?",
            (role_norm, locadora_id, username.strip().lower()),
        )
        return cur.rowcount > 0


def update_password(username: str, password_hash: str) -> bool:
    init_registry_db()
    with _lock, _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, username.strip().lower()),
        )
        return cur.rowcount > 0


def repair_default_inventory_names() -> int:
    init_registry_db()
    changed = 0
    with _lock:
        conn = _connect()
        rows = conn.execute("SELECT id FROM branches WHERE inventory_name = 'default'").fetchall()
        for row in rows:
            conn.execute("UPDATE branches SET inventory_name = ? WHERE id = ?", (row["id"], row["id"]))
            changed += 1
    return changed
