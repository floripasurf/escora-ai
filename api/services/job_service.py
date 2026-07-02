"""Job lifecycle management — SQLite-backed, tenant-scoped by branch_id.

Schema (data/jobs.db):
    jobs(id TEXT PK, branch_id TEXT, status TEXT, filename TEXT,
         office_name TEXT, input_path TEXT,
         output_dxf_path, csv_path, ifc_path, revision_path,
         validated_* paths (6),
         results_data JSON, validated_results JSON,
         revision_data JSON,
         error_message, optimization_mode, inventory_name,
         created_at TEXT, updated_at TEXT)

Public API (unchanged vs. the in-memory version) so routes don't care:
    create_job, get_job, update_job, delete_job, list_jobs
Plus:
    init_db, sweep_orphan_processing, all_jobs (for startup helpers)
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Iterable, List, Optional

from api.config import settings

# Hard wall-clock cap for any single pipeline run. Keep this slightly longer
# than the subprocess timeout so the parent has time to write a precise error
# before the DB watchdog flips orphaned jobs.
PROCESSING_TIMEOUT_SECONDS = settings.pipeline_timeout_seconds + 120

_lock = threading.Lock()

# Fields stored as JSON in SQLite for simplicity.
_JSON_FIELDS = {"results_data", "validated_results", "revision_data"}

# Column order — also defines the full set of valid job fields.
_COLUMNS = (
    "id",
    "branch_id",
    "status",
    "filename",
    "office_name",
    "input_path",
    "output_dxf_path",
    "csv_path",
    "ifc_path",
    "revision_path",
    "validated_dxf_path",
    "validated_csv_path",
    "validated_ifc_path",
    "validated_pdf_path",
    "validated_memoria_path",
    "validated_orcamento_path",
    "results_data",
    "validated_results",
    "revision_data",
    "error_message",
    "status_detail",
    "optimization_mode",
    "inventory_name",
    "created_at",
    "updated_at",
)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL,
    status TEXT NOT NULL,
    filename TEXT NOT NULL,
    office_name TEXT,
    input_path TEXT,
    output_dxf_path TEXT,
    csv_path TEXT,
    ifc_path TEXT,
    revision_path TEXT,
    validated_dxf_path TEXT,
    validated_csv_path TEXT,
    validated_ifc_path TEXT,
    validated_pdf_path TEXT,
    validated_memoria_path TEXT,
    validated_orcamento_path TEXT,
    results_data TEXT,
    validated_results TEXT,
    revision_data TEXT,
    error_message TEXT,
    status_detail TEXT,
    optimization_mode TEXT DEFAULT 'price',
    inventory_name TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_branch ON jobs(branch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
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
        # Migração idempotente para DBs criados antes da coluna existir.
        # NUNCA dentro do _CREATE_SQL: CREATE TABLE IF NOT EXISTS não altera
        # tabela existente, então a coluna nova precisa do ALTER explícito.
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN status_detail TEXT")
        except sqlite3.OperationalError:
            pass  # coluna já existe


def _row_to_job(row: sqlite3.Row) -> dict:
    job: dict = {}
    for key in row.keys():
        val = row[key]
        if key in _JSON_FIELDS and val is not None:
            try:
                job[key] = json.loads(val)
            except Exception:
                job[key] = None
        elif key in ("created_at", "updated_at") and val is not None:
            try:
                job[key] = datetime.fromisoformat(val)
            except Exception:
                job[key] = datetime.utcnow()
        else:
            job[key] = val
    return job


def _serialize(field: str, value: Any) -> Any:
    if value is None:
        return None
    if field in _JSON_FIELDS:
        return json.dumps(value, default=str, ensure_ascii=False)
    if field in ("created_at", "updated_at") and isinstance(value, datetime):
        return value.isoformat()
    return value


def create_job(
    filename: str,
    input_path: str,
    branch_id: str,
    office_name: Optional[str] = None,
) -> dict:
    job_id = uuid.uuid4().hex  # full 32-char UUID, not adivinhável
    now = datetime.utcnow()
    init_db()
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, branch_id, status, filename, office_name,
                              input_path, created_at, updated_at, optimization_mode)
            VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, 'price')
            """,
            (job_id, branch_id, filename, office_name, input_path,
             now.isoformat(), now.isoformat()),
        )
    return get_job(job_id) or {}


def get_job(job_id: str, branch_id: Optional[str] = None) -> Optional[dict]:
    init_db()
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    job = _row_to_job(row)
    if branch_id is not None and job.get("branch_id") != branch_id:
        return None
    return job


def update_job(job_id: str, **kwargs) -> Optional[dict]:
    if not kwargs:
        return get_job(job_id)
    updates = {k: v for k, v in kwargs.items() if k in _COLUMNS and k != "id"}
    if not updates:
        return get_job(job_id)
    updates["updated_at"] = datetime.utcnow()
    assignments = ", ".join(f"{k} = ?" for k in updates.keys())
    values = [_serialize(k, v) for k, v in updates.items()]
    values.append(job_id)
    init_db()
    with _lock, _connect() as conn:
        conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)
    return get_job(job_id)


def delete_job(job_id: str) -> bool:
    init_db()
    with _lock, _connect() as conn:
        cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cur.rowcount > 0


def sweep_stale_processing() -> int:
    """Flip jobs stuck in `processing` past PROCESSING_TIMEOUT_SECONDS to error.

    Called on every list_jobs() so the UI auto-recovers from hung pipelines
    (OOM, infinite loop, mid-flight crash) without needing a restart.
    Returns the number of jobs swept.
    """
    init_db()
    cutoff = (datetime.utcnow() - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS)).isoformat()
    now = datetime.utcnow().isoformat()
    with _lock, _connect() as conn:
        cur = conn.execute(
            """
            UPDATE jobs
               SET status = 'error',
                   error_message = 'Processamento excedeu o tempo limite (provavel timeout/OOM). Tente um arquivo menor ou divida o pavimento.',
                   updated_at = ?
             WHERE status = 'processing'
               AND updated_at < ?
            """,
            (now, cutoff),
        )
        return cur.rowcount


def list_jobs(branch_id: Optional[str] = None) -> List[dict]:
    init_db()
    sweep_stale_processing()
    with _lock, _connect() as conn:
        if branch_id is not None:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE branch_id = ? ORDER BY created_at DESC",
                (branch_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_job(r) for r in rows]


def all_jobs() -> List[dict]:
    return list_jobs()


def sweep_orphan_processing() -> int:
    """Mark any jobs stuck in `processing` as `error` — run at startup.

    A previous process was interrupted mid-run; the pipeline will never resume,
    so the job must be explicitly failed so the engineer sees a clear message.
    Returns the number of jobs swept.
    """
    init_db()
    now = datetime.utcnow().isoformat()
    with _lock, _connect() as conn:
        cur = conn.execute(
            """
            UPDATE jobs
               SET status = 'error',
                   error_message = 'Processamento interrompido por reinicio do servidor. Reenvie o arquivo.',
                   updated_at = ?
             WHERE status IN ('pending', 'processing')
            """,
            (now,),
        )
        return cur.rowcount


def _reset_for_tests() -> None:
    """Test helper: drop and recreate the jobs table."""
    with _lock, _connect() as conn:
        conn.execute("DROP TABLE IF EXISTS jobs")
        conn.executescript(_CREATE_SQL)
