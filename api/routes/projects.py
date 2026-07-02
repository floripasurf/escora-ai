"""Project endpoints para geracao de projetos de alvenaria estrutural.

Endpoints:
    POST /api/v1/projects                          -- Cria projeto a partir de input
    GET  /api/v1/projects/{id}/status               -- Status do projeto
    GET  /api/v1/projects/{id}/download/dxf/{type}  -- Download DXF
    GET  /api/v1/projects/{id}/download/pdf          -- Download memorial PDF
    GET  /api/v1/projects/{id}/download/csv          -- Download BOM CSV
    GET  /api/v1/projects/{id}/download/zip          -- Download pacote completo
    GET  /api/v1/projects/{id}/preview               -- Preview JSON para SVG
"""

import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from typing import Optional

from api.config import settings
from api.deps import get_current_branch
from api.services import project_service
from api.services.project_pipeline_service import process_project
from src.auth.branches import Branch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


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


def _run_project_pipeline(project_id: str, input_data: dict) -> None:
    """Background task: run project generation."""
    output_dir = str(Path(settings.output_dir) / "projects")

    # Run synchronously in background task (simpler than subprocess for now)
    try:
        result = process_project(input_data, project_id, output_dir)
        project_service.finish_project(project_id, result)
    except Exception as e:
        logger.exception(f"Project {project_id} failed")
        project_service.finish_project(project_id, {
            "status": "error",
            "project_id": project_id,
            "error": str(e),
        })


def _require_project_access(project_id: str, branch: Branch) -> dict:
    data = project_service.get_project(project_id, branch_id=branch.id)
    if not data:
        raise HTTPException(404, "Projeto nao encontrado")
    return data


# === Endpoints ===

@router.post("", status_code=201, response_model=ProjectCreateResponse)
async def create_project(
    request: ProjectCreateRequest,
    background_tasks: BackgroundTasks,
    branch: Branch = Depends(get_current_branch),
):
    """Cria um novo projeto de alvenaria estrutural.

    Recebe os dados do formulario e inicia a geracao em background.
    """
    input_data = request.model_dump()
    project = project_service.create_project(input_data, branch)
    project_id = project["id"]
    background_tasks.add_task(_run_project_pipeline, project_id, input_data)

    return ProjectCreateResponse(id=project_id, status="processing")


@router.get("/{project_id}/status", response_model=ProjectStatusResponse)
async def get_project_status(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Retorna status e resumo do projeto."""
    data = _require_project_access(project_id, branch)

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

    data = _require_project_access(project_id, branch)
    if data.get("status") != "done":
        raise HTTPException(400, "Projeto ainda nao concluido")

    key = f"{dxf_type}_dxf_path"
    path = data.get(key)
    if not path or not Path(path).exists():
        raise HTTPException(404, f"DXF {dxf_type} nao encontrado")

    from fastapi.responses import FileResponse
    filename = Path(path).name
    return FileResponse(
        path, media_type="application/dxf", filename=filename
    )


@router.get("/{project_id}/download/pdf")
async def download_pdf(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download memorial de calculo PDF."""
    data = _require_project_access(project_id, branch)
    if data.get("status") != "done":
        raise HTTPException(400, "Projeto ainda nao concluido")

    path = data.get("memorial_pdf_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "PDF nao encontrado")

    from fastapi.responses import FileResponse
    return FileResponse(
        path, media_type="application/pdf", filename=Path(path).name
    )


@router.get("/{project_id}/download/csv")
async def download_csv(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download BOM CSV."""
    data = _require_project_access(project_id, branch)
    if data.get("status") != "done":
        raise HTTPException(400, "Projeto ainda nao concluido")

    path = data.get("bom_csv_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "CSV nao encontrado")

    from fastapi.responses import FileResponse
    return FileResponse(
        path, media_type="text/csv", filename=Path(path).name
    )


@router.get("/{project_id}/download/zip")
async def download_zip(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Download pacote ZIP com todos os arquivos do projeto."""
    data = _require_project_access(project_id, branch)
    if data.get("status") != "done":
        raise HTTPException(400, "Projeto ainda nao concluido")

    path = data.get("zip_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "ZIP nao encontrado")

    from fastapi.responses import FileResponse
    return FileResponse(
        path, media_type="application/zip", filename=Path(path).name
    )


@router.get("/{project_id}/preview")
async def get_preview(
    project_id: str,
    branch: Branch = Depends(get_current_branch),
):
    """Retorna dados JSON para renderizacao SVG da planta."""
    data = _require_project_access(project_id, branch)
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
    data = _require_project_access(project_id, branch)
    if data.get("status") != "done":
        raise HTTPException(400, "Projeto ainda nao concluido")

    path = data.get("ifc_path")
    if not path or not Path(path).exists():
        raise HTTPException(404, "IFC nao encontrado")

    from fastapi.responses import FileResponse
    return FileResponse(
        path, media_type="application/x-step", filename=Path(path).name
    )
