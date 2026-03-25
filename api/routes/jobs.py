"""Job endpoints: upload, status, preview, calculate, approve."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from api.services import job_service, storage
from api.models.schemas import JobCreateResponse, JobStatusResponse

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("", status_code=201, response_model=JobCreateResponse)
async def upload_dxf(
    file: UploadFile = File(...),
    office_name: Optional[str] = Form(None),
):
    if not file.filename.lower().endswith((".dxf", ".dwg")):
        raise HTTPException(400, "Formato nao suportado. Envie .dxf ou .dwg")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Arquivo excede 50MB")

    job = job_service.create_job(file.filename, "")
    input_path = storage.save_upload(content, file.filename, job["id"])
    job_service.update_job(job["id"], input_path=input_path)

    return JobCreateResponse(
        id=job["id"],
        status=job["status"],
        filename=job["filename"],
        created_at=job["created_at"],
    )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_status(job_id: str):
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    return JobStatusResponse(**job)
