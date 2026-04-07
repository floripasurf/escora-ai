"""Job endpoints: upload, process, download, revision upload."""

import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional
from api.services import job_service, storage
from api.services.pipeline_service import process_dxf
from api.services.revision_service import analyze_revision
from api.models.schemas import JobCreateResponse, JobStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _run_pipeline(job_id: str):
    """Background task: run the pipeline on an uploaded DXF."""
    job = job_service.get_job(job_id)
    if not job:
        return

    job_service.update_job(job_id, status="processing")

    try:
        results = process_dxf(job["input_path"], job_id)

        if "error" in results:
            job_service.update_job(job_id, status="error", error_message=results["error"])
            return

        job_service.update_job(
            job_id,
            status="done",
            results_data=results,
            output_dxf_path=results.get("output_dxf_path"),
            csv_path=results.get("csv_path"),
            ifc_path=results.get("ifc_path"),
        )
        logger.info(f"Job {job_id} done: {results['total_shores']} shores")

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        job_service.update_job(job_id, status="error", error_message=str(e))


@router.post("", status_code=201, response_model=JobCreateResponse)
async def upload_dxf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    office_name: Optional[str] = Form(None),
):
    """Upload a DXF file and start processing."""
    if not file.filename.lower().endswith((".dxf", ".dwg")):
        raise HTTPException(400, "Formato nao suportado. Envie .dxf ou .dwg")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Arquivo excede 50MB")

    job = job_service.create_job(file.filename, "")
    input_path = storage.save_upload(content, file.filename, job["id"])
    job_service.update_job(job["id"], input_path=input_path)

    # Process in background
    background_tasks.add_task(_run_pipeline, job["id"])

    return JobCreateResponse(
        id=job["id"],
        status="processing",
        filename=job["filename"],
        created_at=job["created_at"],
    )


@router.get("", response_model=list)
async def list_jobs():
    """List all jobs."""
    jobs = job_service.list_jobs()
    return [
        {
            "id": j["id"],
            "status": j["status"],
            "filename": j["filename"],
            "created_at": j["created_at"].isoformat(),
            "total_shores": j.get("results_data", {}).get("total_shores") if j.get("results_data") else None,
        }
        for j in jobs
    ]


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_status(job_id: str):
    """Get job status and results."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")

    results = job.get("results_data") or {}
    response = {
        "id": job["id"],
        "status": job["status"],
        "filename": job["filename"],
        "error_message": job.get("error_message"),
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "has_output_dxf": job.get("output_dxf_path") is not None,
        "has_csv": job.get("csv_path") is not None,
        "has_ifc": job.get("ifc_path") is not None,
        "has_relatorio": bool(results.get("relatorio")),
        "has_memoria_calculo": bool(results.get("memoria_calculo")),
        "has_orcamento": bool(results.get("orcamento")),
        "has_revision": job.get("revision_path") is not None,
    }

    if results:
        response.update({
            "beam_count": results.get("beam_count"),
            "pillar_count": results.get("pillar_count"),
            "slab_count": results.get("slab_count"),
            "total_shores": results.get("total_shores"),
            "beams": results.get("beams"),
            "slabs": results.get("slabs"),
            "warnings": results.get("warnings"),
        })

    revision = job.get("revision_data")
    if revision:
        response["revision_learnings"] = revision.get("learnings")

    return JobStatusResponse(**response)


@router.get("/{job_id}/download")
async def download_dxf(job_id: str):
    """Download the output DXF with positioned shores."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    output_path = job.get("output_dxf_path")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(404, "Arquivo de saida nao encontrado")

    filename = Path(job["filename"]).stem + "_escoras.dxf"
    return FileResponse(
        output_path,
        media_type="application/dxf",
        filename=filename,
    )


@router.get("/{job_id}/download/csv")
async def download_csv(job_id: str):
    """Download the BOM (Bill of Materials) as CSV."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    csv_path = job.get("csv_path")
    if not csv_path or not Path(csv_path).exists():
        raise HTTPException(404, "Arquivo CSV nao encontrado")

    filename = Path(job["filename"]).stem + "_BOM.csv"
    return FileResponse(
        csv_path,
        media_type="text/csv",
        filename=filename,
    )


@router.get("/{job_id}/download/ifc")
async def download_ifc(job_id: str):
    """Download the IFC (BIM) export with slabs, beams, pillars, shores."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    ifc_path = job.get("ifc_path")
    if not ifc_path or not Path(ifc_path).exists():
        raise HTTPException(404, "Arquivo IFC nao encontrado")

    filename = Path(job["filename"]).stem + ".ifc"
    return FileResponse(
        ifc_path,
        media_type="application/x-step",
        filename=filename,
    )


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its files."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")

    # Clean up files
    import shutil
    from api.config import settings
    job_dir = Path(settings.output_dir) / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)

    upload_path = job.get("input_path")
    if upload_path and Path(upload_path).exists():
        Path(upload_path).unlink(missing_ok=True)

    job_service.delete_job(job_id)
    return {"message": "Job removido com sucesso"}


@router.get("/{job_id}/download/pdf/{report_type}")
async def download_pdf(job_id: str, report_type: str):
    """Download a PDF report (relatorio, memoria_calculo, orcamento)."""
    if report_type not in ("relatorio", "memoria_calculo", "orcamento"):
        raise HTTPException(400, "Tipo invalido. Use: relatorio, memoria_calculo, orcamento")

    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    results = job.get("results_data") or {}
    pdf_path = results.get(report_type)
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(404, f"PDF {report_type} nao encontrado")

    labels = {
        "relatorio": "relatorio",
        "memoria_calculo": "memoria_calculo",
        "orcamento": "orcamento",
    }
    filename = f"{Path(job['filename']).stem}_{labels[report_type]}.pdf"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.post("/{job_id}/revision")
async def upload_revision(
    job_id: str,
    file: UploadFile = File(...),
):
    """Upload the engineer's revised DXF for learning.

    The system compares the original output with the revision to learn:
    - Which shores were added (under-shored areas)
    - Which shores were removed (over-shored areas)
    - Which shores were moved (positioning calibration)
    """
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    if not file.filename.lower().endswith((".dxf",)):
        raise HTTPException(400, "Envie o arquivo .dxf revisado")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, "Arquivo excede 50MB")

    # Save revision
    revision_path = storage.save_upload(content, f"revisao_{file.filename}", job_id)
    job_service.update_job(job_id, revision_path=revision_path)

    # Analyze diff
    original_dxf = job.get("output_dxf_path")
    if not original_dxf or not Path(original_dxf).exists():
        raise HTTPException(500, "Arquivo original nao encontrado para comparacao")

    try:
        diff = analyze_revision(original_dxf, revision_path)
        job_service.update_job(job_id, revision_data=diff)

        return {
            "message": "Revisao recebida e analisada",
            "learnings": diff["learnings"],
            "accuracy_beam": round(diff["accuracy_beam"], 1),
            "accuracy_slab": round(diff["accuracy_slab"], 1),
            "beam_added": diff["beam_added"],
            "beam_removed": diff["beam_removed"],
            "slab_added": diff["slab_added"],
            "slab_removed": diff["slab_removed"],
        }
    except Exception as e:
        logger.exception("Revision analysis failed")
        return {
            "message": "Revisao salva mas analise falhou",
            "error": str(e),
        }
