"""Job endpoints: upload, process, download, revision upload.

All routes are tenant-scoped: the caller's branch is resolved from the
session token (Authorization: Bearer ...) plus X-Branch-Id header via
`get_current_branch`, and jobs belonging to other branches are invisible
(treated as 404).
"""

import logging
import multiprocessing as mp
import os
import platform
from contextlib import contextmanager
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from typing import Optional
from api.config import settings
from api.services import job_service, storage
from api.services import pipeline_service
from api.services.pipeline_service import process_dxf
from api.services.revision_service import analyze_revision
from api.models.schemas import JobCreateResponse, JobStatusResponse, DiagnosticsData


def _sanitize_diagnostics(raw: Optional[dict]) -> dict:
    """Filtra diagnostics para os campos conhecidos de DiagnosticsData.

    Compat: jobs persistidos antes da renomeação de chaves (ex.: vertical_kg_m2)
    têm chaves legadas; como o schema usa extra='forbid', passá-las cruas
    quebraria o endpoint de status (500). Aqui dropamos chaves desconhecidas —
    o drift de código novo continua pego pelo teste de contrato em CI.
    """
    raw = raw or {}
    allowed = set(DiagnosticsData.model_fields)
    return {k: v for k, v in raw.items() if k in allowed}
from api.deps import get_current_branch, require_operator_or_admin
from src.auth.branches import Branch, User
from src.pipeline.learning_store import LearningStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

MAX_FILE_SIZE = settings.max_file_size_mb * 1024 * 1024

def _get_mp_context():
    requested = os.environ.get("ESCORA_MP_START_METHOD")
    if requested:
        return mp.get_context(requested)
    # Force `fork` on Linux/Fly so the child inherits already-loaded modules
    # without paying import cost twice. Avoid fork on macOS: importing Objective-C
    # linked modules after fork can abort the Python process.
    if platform.system() == "Linux":
        return mp.get_context("fork")
    return mp.get_context("spawn")


_MP_CTX = _get_mp_context()


@contextmanager
def _pipeline_execution_lock(job_id: str):
    """Serialize heavy pipeline jobs on a machine.

    A single Fly shared-CPU VM can time out when multiple DXF pipelines run at
    once. Keep queued jobs in `pending`; only the job holding this file lock is
    marked `processing` and consumes the pipeline wall-clock budget.
    """
    import fcntl

    lock_path = settings.data_root / "pipeline.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        logger.info(f"Job {job_id} waiting for pipeline execution lock")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        logger.info(f"Job {job_id} acquired pipeline execution lock")
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            logger.info(f"Job {job_id} released pipeline execution lock")


def _pipeline_worker(job_id: str) -> None:
    """Subprocess entry point — runs the actual pipeline.

    Kept side-effect-only: writes results straight to the jobs DB so the
    parent doesn't need IPC. Any uncaught exception is converted to an
    `error` row before the process exits.
    """
    try:
        job = job_service.get_job(job_id)
        if not job:
            return
        results = process_dxf(
            job["input_path"],
            job_id,
            mode=job.get("optimization_mode", "price"),
            inventory_name=job.get("inventory_name"),
            branch_id=job.get("branch_id"),
        )
        if "error" in results:
            job_service.update_job(job_id, status="error", error_message=results["error"])
            return
        job_service.update_job(
            job_id,
            status="done",
            results_data=results,
            output_dxf_path=results.get("output_dxf_path"),
            dwg_path=results.get("dwg_path"),
            csv_path=results.get("csv_path"),
            ifc_path=results.get("ifc_path"),
        )
        logger.info(f"Job {job_id} done: {results.get('total_shores')} shores")
    except Exception as e:  # pragma: no cover - defensive
        logger.exception(f"Job {job_id} failed in worker")
        try:
            job_service.update_job(job_id, status="error", error_message=str(e))
        except Exception:
            pass


def _run_pipeline(job_id: str) -> None:
    """Background task: spawn a subprocess and enforce a hard wall-clock timeout.

    Why a subprocess and not BackgroundTasks alone:
      - FastAPI BackgroundTasks share the uvicorn process. If the pipeline
        hangs (pathological DXF, infinite loop in shapely, runaway memory),
        there is no way to kill it from inside the same process. The job
        sits in `processing` forever and the UI spins.
      - A `multiprocessing.Process` can be SIGTERM'd / SIGKILL'd from the
        parent the moment we exceed the budget, and the parent then writes
        a clean `error` row to the DB.
      - On OOM the kernel kills only the child, the API stays up.
    """
    with _pipeline_execution_lock(job_id):
        job_service.update_job(job_id, status="processing")
        proc = _MP_CTX.Process(target=_pipeline_worker, args=(job_id,), daemon=True)
        proc.start()
        proc.join(timeout=settings.pipeline_timeout_seconds)
        if proc.is_alive():
            logger.warning(f"Job {job_id} exceeded {settings.pipeline_timeout_seconds}s — killing worker")
            proc.terminate()
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=5)
            job_service.update_job(
                job_id,
                status="error",
                error_message=(
                    "Processamento excedeu o limite de tempo no servidor. "
                    "O arquivo pode exigir otimização adicional; reenvie o arquivo "
                    "ou aguarde a análise técnica."
                ),
            )
            return
        # If the child crashed (OOM kill, segfault) before writing a result row,
        # the job will still be in `processing`. Surface that explicitly.
        if proc.exitcode not in (0, None):
            current = job_service.get_job(job_id) or {}
            if current.get("status") == "processing":
                job_service.update_job(
                    job_id,
                    status="error",
                    error_message=(
                        f"Worker terminou inesperadamente (codigo {proc.exitcode}). "
                        "Provavel falta de memoria — tente um arquivo menor."
                    ),
                )


@router.post("", status_code=201, response_model=JobCreateResponse)
async def upload_dxf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    office_name: Optional[str] = Form(None),
    optimization_mode: Optional[str] = Form("price"),
    branch: Branch = Depends(get_current_branch),
    _: User = Depends(require_operator_or_admin),
):
    """Upload a DXF file and start processing.

    The caller's branch (from session + X-Branch-Id) determines which
    inventory and learning store are used.
    """
    if not file.filename.lower().endswith((".dxf", ".dwg")):
        raise HTTPException(400, "Formato nao suportado. Envie .dxf ou .dwg")

    if optimization_mode not in ("price", "inventory"):
        optimization_mode = "price"

    job = job_service.create_job(file.filename, "", branch_id=branch.id)
    input_path = await storage.save_upload_stream(
        file, file.filename, job["id"], max_bytes=MAX_FILE_SIZE
    )
    job_service.update_job(
        job["id"],
        input_path=input_path,
        optimization_mode=optimization_mode,
        inventory_name=branch.inventory_name,
    )

    # Process in background
    background_tasks.add_task(_run_pipeline, job["id"])

    return JobCreateResponse(
        id=job["id"],
        status="pending",
        filename=job["filename"],
        created_at=job["created_at"],
    )


@router.get("", response_model=list)
async def list_jobs(branch: Branch = Depends(get_current_branch)):
    """List jobs belonging to the caller's branch."""
    jobs = job_service.list_jobs(branch_id=branch.id)
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
async def get_status(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Get job status and results."""
    job_service.sweep_stale_processing()
    job = job_service.get_job(job_id, branch_id=branch.id)
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
        "has_consumption_csv": bool(results.get("consumption_csv_path")),
        "has_revision": job.get("revision_path") is not None,
        "has_validated": job.get("validated_dxf_path") is not None,
        "has_diagrams": bool((job.get("results_data") or {}).get("mermaid_diagrams")),
        "optimization_mode": job.get("optimization_mode"),
        "inventory_name": job.get("inventory_name"),
        "methodology": results.get("methodology"),
    }


    if results:
        response.update({
            "beam_count": results.get("beam_count"),
            "pillar_count": results.get("pillar_count"),
            "slab_count": results.get("slab_count"),
            "total_shores": results.get("total_shores"),
            "warnings": results.get("warnings"),
            "requires_review": results.get("requires_review", False),
            "review_reasons": results.get("review_reasons") or [],
            "diagnostics": _sanitize_diagnostics(results.get("diagnostics")),
            "has_dwg": job.get("dwg_path") is not None,
            "consumption_summary": results.get("consumption_summary"),
        })

    revision = job.get("revision_data")
    if revision:
        response["revision_learnings"] = revision.get("learnings")

    return JobStatusResponse(**response)


@router.get("/{job_id}/download")
async def download_dxf(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download the output DXF with positioned shores."""
    job = job_service.get_job(job_id, branch_id=branch.id)
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


@router.get("/{job_id}/download/dwg")
async def download_dwg(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download the output DWG (converted from DXF via ODA File Converter)."""
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    dwg_path = job.get("dwg_path")
    if not dwg_path or not Path(dwg_path).exists():
        raise HTTPException(404, "Arquivo DWG nao disponivel — ODA File Converter nao instalado no servidor")

    filename = Path(job["filename"]).stem + "_escoras.dwg"
    return FileResponse(
        dwg_path,
        media_type="application/acad",
        filename=filename,
    )


@router.get("/{job_id}/download/csv")
async def download_csv(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download the BOM (Bill of Materials) as CSV."""
    job = job_service.get_job(job_id, branch_id=branch.id)
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


@router.get("/{job_id}/download/consumo")
async def download_consumo(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download the consumption-by-ceiling-height CSV (validation summary)."""
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    results = job.get("results_data") or {}
    consumo_path = results.get("consumption_csv_path")
    if not consumo_path or not Path(consumo_path).exists():
        raise HTTPException(404, "CSV de consumo nao encontrado")

    filename = Path(job["filename"]).stem + "_consumo.csv"
    return FileResponse(
        consumo_path,
        media_type="text/csv",
        filename=filename,
    )


@router.get("/{job_id}/download/ifc")
async def download_ifc(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download the IFC (BIM) export with slabs, beams, pillars, shores."""
    job = job_service.get_job(job_id, branch_id=branch.id)
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


@router.get("/{job_id}/diagrams")
async def get_diagrams(
    job_id: str,
    diagram_type: Optional[str] = None,
    branch: Branch = Depends(get_current_branch),
):
    """Return Mermaid.js diagrams for a completed job.

    Diagram types:
    - decision_flow: árvore de decisão torre vs escora
    - project_summary: resumo com regras disparadas por elemento
    - spacing: espaçamento adaptativo por laje

    Query params:
        diagram_type: optional, return only this diagram type.
                      If omitted, returns all diagrams.

    Response: {"diagrams": {"decision_flow": "...", "project_summary": "...", "spacing": "..."}}
    Render with mermaid.js: mermaid.render('id', diagram_string)
    """
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    results = job.get("results_data") or {}
    diagrams = results.get("mermaid_diagrams") or {}

    if not diagrams:
        raise HTTPException(404, "Diagramas nao disponiveis para este job")

    if diagram_type:
        if diagram_type not in diagrams:
            raise HTTPException(
                400,
                f"Tipo invalido. Disponiveis: {', '.join(diagrams.keys())}",
            )
        return {"diagrams": {diagram_type: diagrams[diagram_type]}}

    return {"diagrams": diagrams}


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
    _: User = Depends(require_operator_or_admin),
):
    """Delete a job and its files."""
    job = job_service.get_job(job_id, branch_id=branch.id)
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
async def download_pdf(
    job_id: str,
    report_type: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download a PDF report (relatorio, memoria_calculo, orcamento)."""
    if report_type not in ("relatorio", "memoria_calculo", "orcamento"):
        raise HTTPException(400, "Tipo invalido. Use: relatorio, memoria_calculo, orcamento")

    job = job_service.get_job(job_id, branch_id=branch.id)
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


@router.get("/{job_id}/download/validated/dxf")
async def download_validated_dxf(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    path = job.get("validated_dxf_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "DXF validado nao encontrado")
    filename = Path(job["filename"]).stem + "_escoras_validated.dxf"
    return FileResponse(path, media_type="application/dxf", filename=filename)


@router.get("/{job_id}/download/validated/csv")
async def download_validated_csv(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    path = job.get("validated_csv_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "CSV validado nao encontrado")
    filename = Path(job["filename"]).stem + "_BOM_validated.csv"
    return FileResponse(path, media_type="text/csv", filename=filename)


@router.get("/{job_id}/download/validated/ifc")
async def download_validated_ifc(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    path = job.get("validated_ifc_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "IFC validado nao encontrado")
    filename = Path(job["filename"]).stem + "_validated.ifc"
    return FileResponse(path, media_type="application/x-step", filename=filename)


@router.get("/{job_id}/download/validated/pdf")
async def download_validated_pdf(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    path = job.get("validated_pdf_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "Relatorio validado nao encontrado")
    filename = Path(job["filename"]).stem + "_relatorio_validated.pdf"
    return FileResponse(path, media_type="application/pdf", filename=filename)


@router.get("/{job_id}/download/validated/memoria")
async def download_validated_memoria(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    path = job.get("validated_memoria_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "Memoria validada nao encontrada")
    filename = Path(job["filename"]).stem + "_memoria_calculo_validated.pdf"
    return FileResponse(path, media_type="application/pdf", filename=filename)


@router.get("/{job_id}/download/validated/orcamento")
async def download_validated_orcamento(
    job_id: str,
    branch: Branch = Depends(get_current_branch),
):
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    path = job.get("validated_orcamento_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "Orcamento validado nao encontrado")
    filename = Path(job["filename"]).stem + "_orcamento_validated.pdf"
    return FileResponse(path, media_type="application/pdf", filename=filename)


@router.post("/{job_id}/revision")
async def upload_revision(
    job_id: str,
    file: UploadFile = File(...),
    branch: Branch = Depends(get_current_branch),
    _: User = Depends(require_operator_or_admin),
):
    """Upload the engineer's revised DXF for learning.

    The system compares the original output with the revision to learn:
    - Which shores were added (under-shored areas)
    - Which shores were removed (over-shored areas)
    - Which shores were moved (positioning calibration)
    """
    job = job_service.get_job(job_id, branch_id=branch.id)
    if not job:
        raise HTTPException(404, "Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(400, "Processamento ainda nao concluido")

    if not file.filename.lower().endswith((".dxf",)):
        raise HTTPException(400, "Envie o arquivo .dxf revisado")

    # Save revision (streamed to disk, never buffered in RAM)
    revision_path = await storage.save_upload_stream(
        file, f"revisao_{file.filename}", job_id, max_bytes=MAX_FILE_SIZE
    )
    job_service.update_job(job_id, revision_path=revision_path)

    # Analyze diff
    original_dxf = job.get("output_dxf_path")
    if not original_dxf or not Path(original_dxf).exists():
        raise HTTPException(500, "Arquivo original nao encontrado para comparacao")

    try:
        diff = analyze_revision(original_dxf, revision_path)
        job_service.update_job(job_id, revision_data=diff)

        try:
            store = LearningStore(branch_id=branch.id)
            store.update_record_with_revision(filename=job["filename"], diff=diff)
            store.save()
        except Exception as learn_err:
            logger.warning(f"Failed to persist revision learnings: {learn_err}")

        validated_paths = {}
        try:
            validated = pipeline_service.regenerate_from_revision(
                original_input_path=job["input_path"],
                revised_input_path=revision_path,
                job_id=job_id,
                branch_id=branch.id,
            )
            if "error" not in validated:
                validated_paths = {
                    "validated_dxf_path": validated.get("output_dxf_path"),
                    "validated_csv_path": validated.get("csv_path"),
                    "validated_ifc_path": validated.get("ifc_path"),
                    "validated_pdf_path": validated.get("relatorio"),
                    "validated_memoria_path": validated.get("memoria_calculo"),
                    "validated_orcamento_path": validated.get("orcamento"),
                    "validated_results": validated,
                }
                job_service.update_job(job_id, **validated_paths)
        except Exception as regen_err:
            logger.exception(f"Validated regeneration failed: {regen_err}")

        return {
            "message": "Revisao recebida e analisada",
            "learnings": diff["learnings"],
            "accuracy_beam": round(diff["accuracy_beam"], 1),
            "accuracy_slab": round(diff["accuracy_slab"], 1),
            "beam_added": diff["beam_added"],
            "beam_removed": diff["beam_removed"],
            "slab_added": diff["slab_added"],
            "slab_removed": diff["slab_removed"],
            "has_validated": bool(validated_paths),
        }
    except Exception as e:
        logger.exception("Revision analysis failed")
        return {
            "message": "Revisao salva mas analise falhou",
            "error": str(e),
        }
