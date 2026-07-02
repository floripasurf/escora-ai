"""Design preview endpoint — synchronous layout generation for real-time editing."""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.models.masonry import DesignInput, SiteAnalysis
from src.layout.solver import solve_layout_interactive
from src.utils.masonry_constants import MIN_ROOM_AREAS, MIN_ROOM_DIMENSION
from api.deps import get_current_user
from api.services.project_pipeline_service import _build_preview

logger = logging.getLogger(__name__)

# Stateless generation endpoints: session required, no X-Branch-Id needed.
router = APIRouter(
    prefix="/api/v1/design",
    tags=["design"],
    dependencies=[Depends(get_current_user)],
)


class DesignPreviewRequest(BaseModel):
    """Request for interactive design preview."""
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
    # Extended fields for design mode
    street_side: str = Field(default="south")
    sun_orientation_deg: float = Field(default=0.0, ge=0.0, le=360.0)
    style: str = Field(default="modern")
    roof_style: str = Field(default="gable")
    privacy_priority: str = Field(default="balanced")
    country: str = Field(default="BR")
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    # Economic construction options
    economy_mode: bool = Field(default=False)
    foundation_type: str = Field(default="sapata_corrida")
    structure_type: str = Field(default="masonry")
    roof_material: str = Field(default="ceramic")
    slab_type: str = Field(default="pre_moldada")
    finish_level: str = Field(default="basic")
    # Template selection
    template_id: Optional[str] = Field(default=None)


@router.post("/alternatives")
def design_alternatives(request: DesignPreviewRequest):
    """Return multiple layout alternatives for the user to choose from.

    Returns compact previews (mini SVG data) for 3-6 templates,
    ranked by compatibility with the user's input.

    Handler síncrono de propósito: FastAPI o executa no threadpool, então a
    geração (CPU-bound) não bloqueia o event loop para os demais clientes.
    """
    try:
        from src.layout.repertoire import select_top_templates

        alternatives = select_top_templates(
            bedrooms=request.bedrooms,
            target_area=request.target_area_m2,
            has_garage=request.has_garage,
            layout_type=request.layout_type,
            lot_width=request.lot_width_m,
            lot_depth=request.lot_depth_m,
            max_results=6,
        )

        results = []
        for tmpl in alternatives:
            # Build mini room summary from template rooms
            rooms_summary = []
            for r in tmpl.get("rooms", []):
                w = r["rel_w"] * tmpl.get("preferred_width_m", 8)
                h = r["rel_h"] * tmpl.get("preferred_depth_m", 8)
                rooms_summary.append({
                    "name": r["name"],
                    "type": r["type"],
                    "area_m2": round(w * h, 1),
                })

            results.append({
                "id": tmpl["id"],
                "name": tmpl.get("_template_name", tmpl["id"]),
                "typology": tmpl.get("_typology", "rectangle"),
                "tags": tmpl.get("_tags", []),
                "score": tmpl.get("_score", 0),
                "area_range": tmpl.get("_area_range", [0, 0]),
                "preferred_width_m": tmpl.get("preferred_width_m", 0),
                "preferred_depth_m": tmpl.get("preferred_depth_m", 0),
                "rooms": rooms_summary,
                "zones": tmpl.get("zones", []),
            })

        return {"alternatives": results, "count": len(results)}

    except Exception as e:
        logger.exception("Alternatives generation failed")
        raise HTTPException(500, f"Erro ao gerar alternativas: {str(e)}")


@router.post("/preview")
def design_preview(request: DesignPreviewRequest):
    """Generate layout preview synchronously for real-time editing.

    This endpoint is fast (~10ms) and returns JSON geometry
    for SVG/3D rendering without generating any files.

    Handler síncrono de propósito: FastAPI o executa no threadpool, então a
    geração (CPU-bound) não bloqueia o event loop para os demais clientes.
    """
    try:
        # Convert to DesignInput (exclude template_id from DesignInput)
        dump = request.model_dump()
        template_id = dump.pop("template_id", None)
        design_input = DesignInput(**dump)

        # If a specific template was requested, force it
        if template_id:
            design_input._forced_template_id = template_id

        # Solve layout (fast, synchronous)
        floor_plan = solve_layout_interactive(design_input)

        # Build preview JSON
        preview = _build_preview(floor_plan)

        # Add extra metadata for the interactive editor
        preview["ceiling_height_m"] = design_input.ceiling_height_m
        preview["roof_style"] = request.roof_style
        preview["street_side"] = request.street_side
        preview["block_size_cm"] = int(design_input.block_size.value)
        preview["country"] = request.country
        preview["total_area_m2"] = round(floor_plan.width_m * floor_plan.depth_m, 1)

        # Construction system choices
        preview["economy_mode"] = request.economy_mode
        preview["construction"] = {
            "foundation": request.foundation_type,
            "structure": request.structure_type,
            "roof_material": request.roof_material,
            "slab": request.slab_type,
            "finish": request.finish_level,
        }

        # Add driveway geometry if garage exists
        if preview.get("vehicle_access"):
            va = preview["vehicle_access"]
            va["street_side"] = request.street_side
            va["lot_width_m"] = request.lot_width_m
            va["lot_depth_m"] = request.lot_depth_m
            # Driveway runs from garage door to lot edge through setback
            gb = va["garage_bounds"]
            if request.street_side == "south":
                va["driveway"] = {
                    "x0": gb["x0"], "y0": -3.0,  # setback zone
                    "x1": gb["x1"], "y1": gb["y0"],
                    "direction": "south",
                }
            elif request.street_side == "north":
                va["driveway"] = {
                    "x0": gb["x0"], "y0": gb["y1"],
                    "x1": gb["x1"], "y1": gb["y1"] + 3.0,
                    "direction": "north",
                }
            elif request.street_side == "west":
                va["driveway"] = {
                    "x0": -3.0, "y0": gb["y0"],
                    "x1": gb["x0"], "y1": gb["y1"],
                    "direction": "west",
                }
            elif request.street_side == "east":
                va["driveway"] = {
                    "x0": gb["x1"], "y0": gb["y0"],
                    "x1": gb["x1"] + 3.0, "y1": gb["y1"],
                    "direction": "east",
                }

        # Validate room dimensions and emit alerts
        alerts = []
        for room in floor_plan.rooms:
            rtype = room.type.value
            area = room.area_m2
            xs = [p[0] for p in room.polygon]
            ys = [p[1] for p in room.polygon]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            min_side = min(w, h)

            min_area = MIN_ROOM_AREAS.get(rtype)
            min_dim = MIN_ROOM_DIMENSION.get(rtype)

            if min_area and area < min_area * 0.95:
                alerts.append({
                    "type": "area",
                    "room": room.name,
                    "message": f"{room.name}: {area:.1f}m² abaixo do mínimo de {min_area:.1f}m²",
                })
            if min_dim and min_side < min_dim * 0.95:
                alerts.append({
                    "type": "dimension",
                    "room": room.name,
                    "message": f"{room.name}: dimensão {min_side:.2f}m abaixo do mínimo de {min_dim:.1f}m",
                })

        if alerts:
            preview["alerts"] = alerts
            preview["alert_summary"] = (
                f"As dimensões do terreno ({request.lot_width_m}×{request.lot_depth_m}m) "
                f"são insuficientes para {request.bedrooms} quarto(s) com conforto. "
                f"Considere reduzir quartos ou aumentar o terreno."
            )

        return preview

    except Exception as e:
        logger.exception("Design preview failed")
        raise HTTPException(500, f"Erro ao gerar preview: {str(e)}")
