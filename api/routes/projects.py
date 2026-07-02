"""Project endpoints para geracao de projetos de alvenaria estrutural.

Endpoints:
    POST /api/v1/projects                          -- Cria projeto a partir de input
    GET  /api/v1/projects/{id}/status               -- Status do projeto
    GET  /api/v1/projects/{id}/download/dxf/{type}  -- Download DXF
    GET  /api/v1/projects/{id}/download/pdf          -- Download memorial PDF
    GET  /api/v1/projects/{id}/download/csv          -- Download BOM CSV
    GET  /api/v1/projects/{id}/download/zip          -- Download pacote completo
    GET  /api/v1/projects/{id}/preview               -- Preview JSON para SVG

Estado persistido em SQLite (api/services/project_service) com escopo por
branch — sobrevive a restarts e nunca vaza entre locadoras.
"""

import logging
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from api.config import settings
from api.deps import get_current_branch, require_operator_or_admin
from api.services import project_service
from api.services.project_pipeline_service import process_project
from src.auth.branches import Branch, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# Keys of the process_project result persisted as project columns.
_RESULT_FIELDS = (
    "status", "summary", "preview", "arch_dxf_path", "struct_dxf_path",
    "memorial_pdf_path", "bom_csv_path", "ifc_path", "zip_path", "error",
)


# === Request/Response schemas ===

class ProjectCreateRequest(BaseModel):
    model_config = {"extra": "ignore"}

    floors: int = Field(default=1, ge=1, le=2)
    target_area_m2: float = Field(ge=30.0, le=100.0)
    bedrooms: int = Field(ge=1, le=4)
    bathrooms: int = Field(default=1, ge=1, le=2)
    layout_type: str = Field(default="open_kitchen")
    has_garage: bool = Field(default=False)
    lot_width_m: float = Field(ge=5.0, le=20.0)
    lot_depth_m: float = Field(ge=10.0, le=40.0)
    block_size: str = Field(default="14")
    region: str = Field(default="sudeste")
    soil_capacity_kpa: float = Field(default=100.0, ge=50.0, le=500.0)
    ceiling_height_m: float = Field(default=2.80, ge=2.50, le=3.20)
    roof_type: str = Field(default="wooden_truss")


class ProjectCreateResponse(BaseModel):
    id: str
    status: str


class ProjectStatusResponse(BaseModel):
    id: str
    status: str
    error: Optional[str] = None
    summary: Optional[dict] = None
    preview: Optional[dict] = None
    has_arch_dxf: bool = False
    has_struct_dxf: bool = False
    has_memorial_pdf: bool = False
    has_bom_csv: bool = False
    has_ifc: bool = False
    has_zip: bool = False


# === Pipeline worker ===

def _run_project_pipeline(project_id: str, input_data: dict) -> None:
    """Background task: run project generation and persist the result."""
    output_dir = str(Path(settings.output_dir) / "projects")

    try:
        result = process_project(input_data, project_id, output_dir)
        updates = {k: result.get(k) for k in _RESULT_FIELDS if k in result}
        updates.setdefault("status", "error")
        project_service.update_project(project_id, **updates)
    except Exception as e:
        logger.exception(f"Project {project_id} failed")
        project_service.update_project(project_id, status="error", error=str(e))


# === Endpoints ===

def _get_project_for_branch(project_id: str, branch: Branch) -> dict:
    """Fetch a project scoped to the caller's branch (404 on cross-tenant),
    mirroring job_service.get_job(job_id, branch_id=...)."""
    data = project_service.get_project(project_id, branch_id=branch.id)
    if not data:
        raise HTTPException(404, "Projeto nao encontrado")
    return data


def _download(data: dict, path_key: str, media_type: str, missing_label: str):
    if data.get("status") != "done":
        raise HTTPException(400, "Projeto ainda nao concluido")
    path = data.get(path_key)
    if not path or not Path(path).exists():
        raise HTTPException(404, f"{missing_label} nao encontrado")
    return FileResponse(path, media_type=media_type, filename=Path(path).name)


@router.post("", status_code=201, response_model=ProjectCreateResponse)
async def create_project(
    request: ProjectCreateRequest,
    background_tasks: BackgroundTasks,
    branch: Branch = Depends(get_current_branch),
    _: User = Depends(require_operator_or_admin),
):
    """Cria um novo projeto de alvenaria estrutural.

    Recebe os dados do formulario e inicia a geracao em background.
    """
    input_data = request.model_dump()
    project = project_service.create_project(branch.id, input_data)
    background_tasks.add_task(
        _run_project_pipeline, project["id"], input_data
    )
    return ProjectCreateResponse(id=project["id"], status="processing")


@router.get("/{project_id}/status", response_model=ProjectStatusResponse)
async def get_project_status(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Retorna status e resumo do projeto."""
    data = _get_project_for_branch(project_id, branch)

    return ProjectStatusResponse(
        id=project_id,
        status=data.get("status", "unknown"),
        error=data.get("error"),
        summary=data.get("summary"),
        preview=data.get("preview"),
        has_arch_dxf=bool(data.get("arch_dxf_path")),
        has_struct_dxf=bool(data.get("struct_dxf_path")),
        has_memorial_pdf=bool(data.get("memorial_pdf_path")),
        has_bom_csv=bool(data.get("bom_csv_path")),
        has_ifc=bool(data.get("ifc_path")),
        has_zip=bool(data.get("zip_path")),
    )


@router.get("/{project_id}/download/dxf/{dxf_type}")
async def download_dxf(
    project_id: str,
    dxf_type: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download DXF (arch = arquitetonico, struct = estrutural)."""
    if dxf_type not in ("arch", "struct"):
        raise HTTPException(400, "Tipo invalido. Use: arch, struct")
    data = _get_project_for_branch(project_id, branch)
    return _download(data, f"{dxf_type}_dxf_path", "application/dxf", f"DXF {dxf_type}")


@router.get("/{project_id}/download/pdf")
async def download_pdf(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download memorial de calculo PDF."""
    data = _get_project_for_branch(project_id, branch)
    return _download(data, "memorial_pdf_path", "application/pdf", "PDF")


@router.get("/{project_id}/download/csv")
async def download_csv(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download BOM CSV."""
    data = _get_project_for_branch(project_id, branch)
    return _download(data, "bom_csv_path", "text/csv", "CSV")


@router.get("/{project_id}/download/zip")
async def download_zip(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download pacote ZIP com todos os arquivos do projeto."""
    data = _get_project_for_branch(project_id, branch)
    return _download(data, "zip_path", "application/zip", "ZIP")


@router.get("/{project_id}/preview")
async def get_preview(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Retorna dados JSON para renderizacao SVG da planta."""
    data = _get_project_for_branch(project_id, branch)
    if data.get("status") != "done":
        raise HTTPException(400, "Projeto ainda nao concluido")
    preview = data.get("preview")
    if not preview:
        raise HTTPException(404, "Preview nao disponivel")
    return preview


@router.get("/{project_id}/download/ifc")
async def download_ifc(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download IFC BIM model."""
    data = _get_project_for_branch(project_id, branch)
    return _download(data, "ifc_path", "application/x-step", "IFC")
