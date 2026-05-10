"""SQLite-backed project store for masonry project generation."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from api.config import settings

_lock = threading.Lock()
_conn_cache: sqlite3.Connection | None = None


def _db_path() -> Path:
    root = settings.data_root
    root.mkdir(parents=True, exist_ok=True)
    return root / "projects.db"


def _conn() -> sqlite3.Connection:
    global _conn_cache
    if _conn_cache is not None:
        try:
            _conn_cache.execute("SELECT 1")
            return _conn_cache
        except Exception:
            _conn_cache = None

    conn = sqlite3.connect(str(_db_path()), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _conn_cache = conn
    return conn


def init_db() -> None:
    with _lock, _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                locadora_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                status TEXT NOT NULL,
                input_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_branch ON projects(branch_id, created_at DESC)"
        )


def create_project(
    *,
    project_id: str,
    locadora_id: str,
    branch_id: str,
    input_data: dict[str, Any],
) -> None:
    init_db()
    now = time.time()
    result = {"status": "processing", "project_id": project_id}
    with _lock, _conn() as conn:
        conn.execute(
            """
            INSERT INTO projects (
                id, locadora_id, branch_id, status, input_json, result_json, error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                locadora_id,
                branch_id,
                "processing",
                json.dumps(input_data, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                None,
                now,
                now,
            ),
        )


def update_project_result(
    *,
    project_id: str,
    result: dict[str, Any],
) -> None:
    init_db()
    status = str(result.get("status", "unknown"))
    error = result.get("error")
    with _lock, _conn() as conn:
        conn.execute(
            """
            UPDATE projects
            SET status = ?, result_json = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                json.dumps(result, ensure_ascii=False),
                error,
                time.time(),
                project_id,
            ),
        )


def get_project(project_id: str, *, branch_id: str) -> dict[str, Any] | None:
    init_db()
    with _lock, _conn() as conn:
        row = conn.execute(
            "SELECT result_json FROM projects WHERE id = ? AND branch_id = ?",
            (project_id, branch_id),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["result_json"])


def _reset_for_tests() -> None:
    global _conn_cache
    if _conn_cache is not None:
        try:
            _conn_cache.close()
        except Exception:
            pass
        _conn_cache = None
