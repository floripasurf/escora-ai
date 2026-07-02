"""Masonry project lifecycle — SQLite-backed, tenant-scoped by branch_id.

Same pattern as job_service (WAL, JSON fields, 404-por-tenant via
branch_id=None check) so routes don't care about the storage. Table lives in
the SAME jobs.db file, so the existing backup script already covers it.

Replaces the in-memory `_project_store` dict that lost every project on each
`launchctl kickstart` and had no tenant scoping.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any, List, Optional

from api.config import settings

_lock = threading.Lock()

_JSON_FIELDS = {"input_data", "summary", "preview"}

_COLUMNS = (
    "id",
    "branch_id",
    "status",
    "input_data",
    "summary",
    "preview",
    "arch_dxf_path",
    "struct_dxf_path",
    "memorial_pdf_path",
    "bom_csv_path",
    "ifc_path",
    "zip_path",
    "error",
    "created_at",
    "updated_at",
)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    status TEXT NOT NULL,
    input_data TEXT,
    summary TEXT,
    preview TEXT,
    arch_dxf_path TEXT,
    struct_dxf_path TEXT,
    memorial_pdf_path TEXT,
    bom_csv_path TEXT,
    ifc_path TEXT,
    zip_path TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_branch ON projects(branch_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
"""


def _connect() -> sqlite3.Connection:
    path = settings.jobs_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.executescript(_CREATE_SQL)


def _row_to_project(row: sqlite3.Row) -> dict:
    project: dict = {}
    for key in row.keys():
        val = row[key]
        if key in _JSON_FIELDS and val is not None:
            try:
                project[key] = json.loads(val)
            except Exception:
                project[key] = None
        else:
            project[key] = val
    return project


def _serialize(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in _JSON_FIELDS:
        return json.dumps(value, default=str, ensure_ascii=False)
    return value


def create_project(branch_id: str, input_data: dict) -> dict:
    project_id = uuid.uuid4().hex
    now = datetime.utcnow().isoformat()
    init_db()
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, branch_id, status, input_data,
                                  created_at, updated_at)
            VALUES (?, ?, 'processing', ?, ?, ?)
            """,
            (project_id, branch_id,
             _serialize("input_data", input_data), now, now),
        )
    return get_project(project_id) or {}


def get_project(project_id: str, branch_id: Optional[str] = None) -> Optional[dict]:
    init_db()
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    if row is None:
        return None
    project = _row_to_project(row)
    if branch_id is not None and project.get("branch_id") != branch_id:
        return None
    return project


def update_project(project_id: str, **kwargs) -> Optional[dict]:
    updates = {k: v for k, v in kwargs.items() if k in _COLUMNS and k != "id"}
    if not updates:
        return get_project(project_id)
    updates["updated_at"] = datetime.utcnow().isoformat()
    assignments = ", ".join(f"{k} = ?" for k in updates.keys())
    values = [_serialize(k, v) for k, v in updates.items()]
    values.append(project_id)
    init_db()
    with _lock, _connect() as conn:
        conn.execute(f"UPDATE projects SET {assignments} WHERE id = ?", values)
    return get_project(project_id)


def sweep_orphan_processing() -> int:
    """Mark projects stuck in `processing` as `error` — run at startup."""
    init_db()
    now = datetime.utcnow().isoformat()
    with _lock, _connect() as conn:
        cur = conn.execute(
            """
            UPDATE projects
               SET status = 'error',
                   error = 'Geracao interrompida por reinicio do servidor. Gere o projeto novamente.',
                   updated_at = ?
             WHERE status = 'processing'
            """,
            (now,),
        )
        return cur.rowcount


def list_projects(branch_id: Optional[str] = None) -> List[dict]:
    init_db()
    with _lock, _connect() as conn:
        if branch_id is not None:
            rows = conn.execute(
                "SELECT * FROM projects WHERE branch_id = ? ORDER BY created_at DESC",
                (branch_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_project(r) for r in rows]


def _reset_for_tests() -> None:
    """Test helper: drop and recreate the projects table."""
    with _lock, _connect() as conn:
        conn.execute("DROP TABLE IF EXISTS projects")
        conn.executescript(_CREATE_SQL)
