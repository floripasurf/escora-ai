"""Job lifecycle management."""

import uuid
from datetime import datetime
from typing import Optional


# In-memory store for MVP (replace with DB in production)
_jobs: dict = {}


def create_job(filename: str, input_path: str, office_name: Optional[str] = None) -> dict:
    job_id = str(uuid.uuid4())[:8]
    job = {
        "id": job_id,
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
    }
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs) -> Optional[dict]:
    job = _jobs.get(job_id)
    if job:
        job.update(kwargs)
        job["updated_at"] = datetime.utcnow()
    return job


def list_jobs() -> list:
    return sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)
