"""Job lifecycle management (tenant-scoped by branch_id)."""

import uuid
from datetime import datetime
from typing import Optional


# In-memory store for MVP (replace with DB in production).
# Key = job_id (globally unique), value = job dict including branch_id.
_jobs: dict = {}


def create_job(
    filename: str,
    input_path: str,
    branch_id: str,
    office_name: Optional[str] = None,
) -> dict:
    job_id = str(uuid.uuid4())[:8]
    job = {
        "id": job_id,
        "branch_id": branch_id,
        "status": "pending",
        "filename": filename,
        "office_name": office_name,
        "input_path": input_path,
        "output_dxf_path": None,
        "revision_path": None,
        "results_data": None,
        "error_message": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "optimization_mode": "price",
        "inventory_name": None,
        "validated_dxf_path": None,
        "validated_csv_path": None,
        "validated_ifc_path": None,
        "validated_pdf_path": None,
        "validated_memoria_path": None,
        "validated_orcamento_path": None,
        "validated_results": None,
    }
    _jobs[job_id] = job
    return job


def get_job(job_id: str, branch_id: Optional[str] = None) -> Optional[dict]:
    """Fetch job by id. If branch_id is provided, returns None when the job
    belongs to a different branch (tenant isolation)."""
    job = _jobs.get(job_id)
    if job is None:
        return None
    if branch_id is not None and job.get("branch_id") != branch_id:
        return None
    return job


def update_job(job_id: str, **kwargs) -> Optional[dict]:
    job = _jobs.get(job_id)
    if job:
        job.update(kwargs)
        job["updated_at"] = datetime.utcnow()
    return job


def delete_job(job_id: str) -> bool:
    if job_id in _jobs:
        del _jobs[job_id]
        return True
    return False


def list_jobs(branch_id: Optional[str] = None) -> list:
    """List jobs, optionally filtered to one branch."""
    jobs = _jobs.values()
    if branch_id is not None:
        jobs = [j for j in jobs if j.get("branch_id") == branch_id]
    return sorted(jobs, key=lambda j: j["created_at"], reverse=True)
