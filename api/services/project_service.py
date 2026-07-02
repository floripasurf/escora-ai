"""Project lifecycle storage — SQLite-backed and branch-scoped."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any, List, Optional

from api.config import settings
from src.auth.branches import Branch

_lock = threading.Lock()

_JSON_FIELDS = {"input_data", "results_data"}

_COLUMNS = (
    "id",
    "branch_id",
    "locadora_id",
    "status",
    "input_data",
    "results_data",
    "error",
    "created_at",
    "updated_at",
)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    locadora_id TEXT NOT NULL,
    status TEXT NOT NULL,
    input_data TEXT NOT NULL,
    results_data TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_branch ON projects(branch_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
"""


def _connect() -> sqlite3.Connection:
    path = settings.projects_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.executescript(_CREATE_SQL)


def _serialize(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in _JSON_FIELDS:
        return json.dumps(value, default=str, ensure_ascii=False)
    if field in ("created_at", "updated_at") and isinstance(value, datetime):
        return value.isoformat()
    return value


def _row_to_project(row: sqlite3.Row) -> dict:
    project: dict[str, Any] = {}
    for key in row.keys():
        val = row[key]
        if key in _JSON_FIELDS and val is not None:
            try:
                project[key] = json.loads(val)
            except Exception:
                project[key] = {}
        elif key in ("created_at", "updated_at") and val is not None:
            try:
                project[key] = datetime.fromisoformat(val)
            except Exception:
                project[key] = datetime.utcnow()
        else:
            project[key] = val

    results = project.get("results_data")
    if isinstance(results, dict):
        project.update(results)
    if project.get("error"):
        project["error"] = project["error"]
    return project


def create_project(input_data: dict, branch: Branch) -> dict:
    project_id = uuid.uuid4().hex
    now = datetime.utcnow()
    init_db()
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT INTO projects (
                id, branch_id, locadora_id, status, input_data,
                created_at, updated_at
            )
            VALUES (?, ?, ?, 'processing', ?, ?, ?)
            """,
            (
                project_id,
                branch.id,
                branch.locadora_id,
                _serialize("input_data", input_data),
                now.isoformat(),
                now.isoformat(),
            ),
        )
    return get_project(project_id) or {}


def get_project(project_id: str, branch_id: Optional[str] = None) -> Optional[dict]:
    init_db()
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        return None
    project = _row_to_project(row)
    if branch_id is not None and project.get("branch_id") != branch_id:
        return None
    return project


def update_project(project_id: str, **kwargs) -> Optional[dict]:
    if not kwargs:
        return get_project(project_id)
    updates = {k: v for k, v in kwargs.items() if k in _COLUMNS and k != "id"}
    if not updates:
        return get_project(project_id)
    updates["updated_at"] = datetime.utcnow()
    assignments = ", ".join(f"{key} = ?" for key in updates.keys())
    values = [_serialize(key, value) for key, value in updates.items()]
    values.append(project_id)
    init_db()
    with _lock, _connect() as conn:
        conn.execute(f"UPDATE projects SET {assignments} WHERE id = ?", values)
    return get_project(project_id)


def finish_project(project_id: str, result: dict) -> Optional[dict]:
    results_data = {
        key: value
        for key, value in result.items()
        if key not in {"status", "project_id", "error"}
    }
    return update_project(
        project_id,
        status=result.get("status", "done"),
        error=result.get("error"),
        results_data=results_data,
    )


def list_projects(branch_id: Optional[str] = None) -> List[dict]:
    init_db()
    with _lock, _connect() as conn:
        if branch_id is None:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects WHERE branch_id = ? ORDER BY created_at DESC",
                (branch_id,),
            ).fetchall()
    return [_row_to_project(row) for row in rows]


def sweep_orphan_processing() -> int:
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


def clear_memory_cache_for_tests() -> None:
    """Compatibility hook: project storage is persistent, not in-process."""
    return None


def _reset_for_tests() -> None:
    with _lock, _connect() as conn:
        conn.execute("DROP TABLE IF EXISTS projects")
        conn.executescript(_CREATE_SQL)
