"""Drawing API — generate NBR-compliant technical drawings from specifications."""

import logging
import tempfile
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.drawing import TechnicalSheet, NBR
from src.drawing.nbr import HatchMaterial, ProjectionSystem
from src.drawing.sheet import TitleBlockInfo
from src.drawing.perspectives import (
    draw_isometric_box, draw_isometric_from_walls,
    draw_cavaleira_box, CavaleiraConfig, draw_elevation,
)
from src.drawing.views import SectionCut, generate_section_from_walls

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/drawing", tags=["drawing"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class WallSpec(BaseModel):
    """Wall specification."""
    x1: float
    y1: float
    x2: float
    y2: float
    height: float = 2.80
    thickness: float = 0.15
    is_structural: bool = True


class OpeningSpec(BaseModel):
    """Door/window specification."""
    type: str = Field(description="'door' or 'window'")
    x: float
    y: float
    width: float
    height: float = 1.20
    sill_height: float = 1.00
    angle: float = 0.0
    opening_side: str = "left"


class DimensionSpec(BaseModel):
    """Dimension specification."""
    points: List[List[float]] = Field(description="List of [x,y] points")
    offset: float = -0.5
    angle: float = 0.0
    add_total: bool = True


class SectionSpec(BaseModel):
    """Section cut specification."""
    label: str = "A"
    start: List[float] = Field(description="[x, y] start of cutting plane")
    end: List[float] = Field(description="[x, y] end of cutting plane")
    direction: str = "north"


class TitleBlockSpec(BaseModel):
    """Title block information."""
    project: str = ""
    drawing_title: str = ""
    drawing_number: str = ""
    author: str = ""
    responsible: str = ""
    crea_number: str = ""
    date: str = ""
    revision: str = "0"
    client: str = ""
    location: str = ""


class FloorPlanRequest(BaseModel):
    """Request for floor plan drawing generation."""
    format: str = Field(default="A2", description="Sheet format: A0-A4")
    scale: str = Field(default="1:50", description="Drawing scale")
    walls: List[WallSpec]
    openings: List[OpeningSpec] = []
    dimensions: List[DimensionSpec] = []
    sections: List[SectionSpec] = []
    room_labels: List[dict] = Field(default=[], description="[{name, x, y, area_m2}]")
    title_block: Optional[TitleBlockSpec] = None
    include_isometric: bool = False
    include_elevation: bool = False
    elevation_direction: str = "south"


class SimpleDrawingRequest(BaseModel):
    """Simplified request for quick drawing generation."""
    width_m: float = Field(ge=3.0, le=30.0)
    depth_m: float = Field(ge=3.0, le=40.0)
    rooms: List[dict] = Field(
        description="List of {name, x, y, w, h} rooms"
    )
    wall_thickness: float = 0.15
    ceiling_height: float = 2.80
    format: str = "A2"
    scale: str = "1:50"
    project_name: str = ""
    author: str = ""
    views: List[str] = Field(
        default=["plan"],
        description="Views to generate: plan, section, elevation, isometric"
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/floor-plan")
async def generate_floor_plan(request: FloorPlanRequest):
    """Generate a complete floor plan DXF from wall/opening specifications.

    Returns the DXF file as a download.
    """
    try:
        sheet = TechnicalSheet(request.format, scale=request.scale)

        # Title block
        if request.title_block:
            tb = request.title_block
            sheet.add_title_block(TitleBlockInfo(
                project=tb.project,
                drawing_title=tb.drawing_title,
                drawing_number=tb.drawing_number,
                author=tb.author,
                responsible=tb.responsible or tb.author,
                crea_number=tb.crea_number,
                date=tb.date,
                revision=tb.revision,
                scale_str=request.scale,
                sheet_format=request.format,
                client=tb.client,
                location=tb.location,
            ))

        # Draw walls
        for w in request.walls:
            sheet.draw_wall(
                (w.x1, w.y1), (w.x2, w.y2),
                thickness=w.thickness,
                is_structural=w.is_structural,
            )

        # Draw openings
        for o in request.openings:
            if o.type == "door":
                sheet.draw_door(
                    (o.x, o.y), width=o.width,
                    angle=o.angle, opening_side=o.opening_side,
                )
            elif o.type == "window":
                # Window needs two endpoints — derive from position + width + angle
                import math
                cos_a = math.cos(math.radians(o.angle))
                sin_a = math.sin(math.radians(o.angle))
                p1 = (o.x, o.y)
                p2 = (o.x + o.width * cos_a, o.y + o.width * sin_a)
                sheet.draw_window(p1, p2, wall_thickness=0.15)

        # Room labels
        for rl in request.room_labels:
            sheet.add_room_label(
                (rl["x"], rl["y"]),
                rl["name"],
                rl.get("area_m2", 0),
            )

        # Dimensions
        for d in request.dimensions:
            pts = [(p[0], p[1]) for p in d.points]
            sheet.add_chain_dim(
                pts, offset=d.offset, angle=d.angle,
                add_total=d.add_total,
            )

        # Cutting planes
        for s in request.sections:
            sheet.add_cutting_plane(
                tuple(s.start), tuple(s.end), label=s.label,
            )

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            path = sheet.save(f.name)

        return FileResponse(
            path,
            media_type="application/dxf",
            filename="planta_baixa.dxf",
        )

    except Exception as e:
        logger.exception("Floor plan generation failed")
        raise HTTPException(500, f"Erro ao gerar planta: {str(e)}")


@router.post("/section")
async def generate_section(request: FloorPlanRequest):
    """Generate a building section (corte) DXF."""
    try:
        if not request.sections:
            raise HTTPException(400, "No section cuts defined")

        sheet = TechnicalSheet(request.format, scale=request.scale)

        if request.title_block:
            tb = request.title_block
            sheet.add_title_block(TitleBlockInfo(
                project=tb.project,
                drawing_title=tb.drawing_title or f"CORTE {request.sections[0].label}",
                drawing_number=tb.drawing_number,
                author=tb.author,
                date=tb.date,
                scale_str=request.scale,
                sheet_format=request.format,
            ))

        # Convert walls to section format
        walls_data = [
            ((w.x1, w.y1), (w.x2, w.y2), w.height, w.thickness)
            for w in request.walls
        ]

        for i, s in enumerate(request.sections):
            cut = SectionCut(
                label=s.label,
                start=tuple(s.start),
                end=tuple(s.end),
                direction=s.direction,
            )
            origin_y = i * 5.0  # Stack sections vertically
            generate_section_from_walls(
                sheet, walls_data, cut,
                origin=(0.05, 0.05 + origin_y),
            )

        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            path = sheet.save(f.name)

        return FileResponse(
            path,
            media_type="application/dxf",
            filename="corte.dxf",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Section generation failed")
        raise HTTPException(500, f"Erro ao gerar corte: {str(e)}")


@router.post("/perspective")
async def generate_perspective(request: FloorPlanRequest):
    """Generate an isometric perspective DXF."""
    try:
        sheet = TechnicalSheet(request.format, scale=request.scale)

        if request.title_block:
            tb = request.title_block
            sheet.add_title_block(TitleBlockInfo(
                project=tb.project,
                drawing_title="PERSPECTIVA ISOMETRICA",
                author=tb.author,
                date=tb.date,
                scale_str=request.scale,
                sheet_format=request.format,
            ))

        origin = (0.15, 0.05)

        # Draw each wall as isometric box
        for w in request.walls:
            dx = w.x2 - w.x1
            dy = w.y2 - w.y1
            length = (dx**2 + dy**2) ** 0.5

            if abs(dx) > abs(dy):
                draw_isometric_box(
                    sheet, origin,
                    min(w.x1, w.x2), w.y1 - w.thickness / 2, 0,
                    abs(dx), w.thickness, w.height,
                )
            else:
                draw_isometric_box(
                    sheet, origin,
                    w.x1 - w.thickness / 2, min(w.y1, w.y2), 0,
                    w.thickness, abs(dy), w.height,
                )

        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
            path = sheet.save(f.name)

        return FileResponse(
            path,
            media_type="application/dxf",
            filename="perspectiva.dxf",
        )

    except Exception as e:
        logger.exception("Perspective generation failed")
        raise HTTPException(500, f"Erro ao gerar perspectiva: {str(e)}")


@router.get("/formats")
async def list_formats():
    """List available sheet formats and scales."""
    return {
        "formats": {
            f.name: {
                "width_mm": f.width_mm,
                "height_mm": f.height_mm,
                "margin_left_mm": f.margin_left_mm,
                "margin_other_mm": f.margin_other_mm,
                "legend_width_mm": f.legend_width_mm,
            }
            for f in NBR.SheetFormat
        },
        "scales": {
            "reduction": NBR.Scale.REDUCTION,
            "natural": NBR.Scale.NATURAL,
            "amplification": NBR.Scale.AMPLIFICATION,
        },
        "line_types": [
            {"code": lt.name, "name": lt.ezdxf_name, "description": lt.description}
            for lt in NBR.LineType
        ],
        "hatch_materials": [m.name for m in HatchMaterial],
    }
