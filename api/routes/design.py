"""Design preview endpoint — synchronous layout generation for real-time editing."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.models.masonry import DesignInput, SiteAnalysis
from src.layout.solver import solve_layout_interactive
from api.services.project_pipeline_service import _build_preview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/design", tags=["design"])


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


@router.post("/preview")
async def design_preview(request: DesignPreviewRequest):
    """Generate layout preview synchronously for real-time editing.

    This endpoint is fast (~10ms) and returns JSON geometry
    for SVG/3D rendering without generating any files.
    """
    try:
        # Convert to DesignInput
        design_input = DesignInput(**request.model_dump())

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

        return preview

    except Exception as e:
        logger.exception("Design preview failed")
        raise HTTPException(500, f"Erro ao gerar preview: {str(e)}")
