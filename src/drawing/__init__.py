"""Professional technical drawing engine — ABNT/NBR compliant DXF output.

Generates technical drawings following Brazilian standards:
- NBR 10068: Sheet formats and margins
- NBR 8403: Line types and widths
- NBR 8196: Scales
- NBR 8402: Lettering
- NBR 10126: Cotagem (dimensioning)
- NBR 12298: Hachuras (hatching)
- NBR 10067: Orthographic projections (1st diedro)
- NBR 6492: Architectural drawing representation

Usage:
    from src.drawing import TechnicalSheet, NBR

    sheet = TechnicalSheet("A1", scale="1:50")
    sheet.add_title_block(project="Residencia", author="Eng. Silva")
    sheet.draw_wall(p1, p2, thickness=0.15)
    sheet.add_dimension(p1, p2, offset=0.5)
    sheet.save("planta_baixa.dxf")
"""

from .nbr import NBR, SheetFormat, LineType, Scale
from .sheet import TechnicalSheet
from .primitives import DimensionStyle, HatchPattern
from .building_model import BuildingModel
from .materials import (
    WallMaterial, SlabMaterial, RoofMaterial, FoundationMaterial,
    WALL_MATERIALS, SLAB_MATERIALS, ROOF_MATERIALS, FOUNDATION_MATERIALS,
)
from .auto_dim import auto_dimension_plan, auto_dimension_section
from .paper_space import PaperSpaceLayout
from .sketch_reader import read_sketch, read_sketch_to_dxf

__all__ = [
    "NBR",
    "SheetFormat",
    "LineType",
    "Scale",
    "TechnicalSheet",
    "DimensionStyle",
    "HatchPattern",
    "BuildingModel",
    "WallMaterial",
    "SlabMaterial",
    "RoofMaterial",
    "FoundationMaterial",
    "WALL_MATERIALS",
    "SLAB_MATERIALS",
    "ROOF_MATERIALS",
    "FOUNDATION_MATERIALS",
    "auto_dimension_plan",
    "auto_dimension_section",
    "PaperSpaceLayout",
    "read_sketch",
    "read_sketch_to_dxf",
]
