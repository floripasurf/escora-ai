"""Test script — generates sample technical drawings to validate the NBR engine.

Creates:
1. A simple floor plan with walls, doors, windows, dimensions
2. An isometric perspective of the same building
3. A building section (corte)
4. An elevation (fachada)

All output follows ABNT/NBR standards.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.drawing import TechnicalSheet, NBR
from src.drawing.nbr import HatchMaterial, ProjectionSystem, SectionType, LineType
from src.drawing.primitives import HatchPattern, add_section_hatch
from src.drawing.perspectives import (
    draw_isometric_box, draw_cavaleira_box, CavaleiraConfig,
    draw_elevation,
)
from src.drawing.views import SectionCut, generate_section_from_walls
from src.drawing.sheet import TitleBlockInfo

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "drawing_tests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def test_floor_plan():
    """Generate a simple 2-bedroom floor plan."""
    print("Generating floor plan...")

    sheet = TechnicalSheet("A2", scale="1:50")

    # Title block
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="PLANTA BAIXA - PAVIMENTO TERREO",
        drawing_number="01/05",
        author="Escora.AI",
        responsible="Eng. Demo",
        date="2026-04-13",
        scale_str="1:50",
        sheet_format="A2",
    ))

    # External walls (7m x 10m house)
    W = 0.15  # wall thickness
    walls = [
        # External perimeter
        ((0, 0), (7, 0)),       # South wall
        ((7, 0), (7, 10)),      # East wall
        ((0, 10), (7, 10)),     # North wall
        ((0, 0), (0, 10)),      # West wall
        # Internal walls
        ((0, 5), (4, 5)),       # Social/intimate division
        ((4, 0), (4, 5)),       # Corridor east wall
        ((4, 5), (4, 10)),      # Corridor east wall continued
        ((0, 7.5), (4, 7.5)),   # Bedroom division
    ]

    for p1, p2 in walls:
        sheet.draw_wall(p1, p2, thickness=W)

    # Doors
    sheet.draw_door((1.0, 0.0), width=0.80, angle=90)     # Front door
    sheet.draw_door((2.0, 5.0), width=0.70, angle=0)      # Kitchen door
    sheet.draw_door((1.5, 7.5), width=0.70, angle=0)      # Bedroom 1 door
    sheet.draw_door((4.0, 3.0), width=0.70, angle=180)    # Bathroom door

    # Windows
    sheet.draw_window((1.5, 0.0), (3.5, 0.0))             # Living room window
    sheet.draw_window((5.0, 0.0), (6.5, 0.0))             # Kitchen window
    sheet.draw_window((0.0, 6.0), (0.0, 7.0))             # Bedroom 1 window
    sheet.draw_window((0.0, 8.5), (0.0, 9.5))             # Bedroom 2 window

    # Room labels
    sheet.add_room_label((2.0, 2.5), "SALA/COZINHA", 20.0)
    sheet.add_room_label((5.5, 2.5), "BANHEIRO", 4.5)
    sheet.add_room_label((2.0, 6.25), "QUARTO 1", 10.0)
    sheet.add_room_label((2.0, 8.75), "QUARTO 2", 10.0)
    sheet.add_room_label((5.5, 7.5), "SERVICO", 7.5)

    # Dimensions — horizontal (bottom)
    sheet.add_chain_dim(
        [(0, 0), (4, 0), (7, 0)],
        offset=-0.8,
        angle=0,
    )

    # Dimensions — vertical (left)
    sheet.add_chain_dim(
        [(0, 0), (0, 5), (0, 7.5), (0, 10)],
        offset=-0.8,
        angle=90,
    )

    # Centerlines for windows
    sheet.draw_centerline((-0.3, 6.5), (0.3, 6.5))
    sheet.draw_centerline((-0.3, 9.0), (0.3, 9.0))

    # Cutting plane indicator
    sheet.add_cutting_plane((-.5, 5), (7.5, 5), label="A")

    # North arrow
    sheet.add_text((8, 9), "N", height=0.3, color=1)
    sheet.draw_line((8.1, 8.5), (8.1, 8.8), layer="TEXTO", color=1)

    path = sheet.save(str(OUTPUT_DIR / "01_planta_baixa.dxf"))
    print(f"  Saved: {path}")
    return walls


def test_isometric():
    """Generate an isometric view of the building."""
    print("Generating isometric perspective...")

    sheet = TechnicalSheet("A3", scale="1:50")
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="PERSPECTIVA ISOMETRICA",
        drawing_number="04/05",
        author="Escora.AI",
        date="2026-04-13",
        scale_str="1:50",
        sheet_format="A3",
    ))

    origin = (0.15, 0.05)  # Sheet position
    h = 2.80  # Wall height

    # External walls as boxes
    draw_isometric_box(sheet, origin, 0, 0, 0, 7, 0.15, h)   # South
    draw_isometric_box(sheet, origin, 6.85, 0, 0, 0.15, 10, h)  # East
    draw_isometric_box(sheet, origin, 0, 9.85, 0, 7, 0.15, h)  # North
    draw_isometric_box(sheet, origin, 0, 0, 0, 0.15, 10, h)   # West

    # Internal walls
    draw_isometric_box(sheet, origin, 0, 4.85, 0, 4, 0.15, h, draw_hidden=True)
    draw_isometric_box(sheet, origin, 3.85, 0, 0, 0.15, 5, h, draw_hidden=True)

    # Roof (simplified as a flat slab)
    draw_isometric_box(sheet, origin, -0.3, -0.3, h, 7.6, 10.6, 0.12, color=1)

    # Label
    sheet.add_text(origin, "PERSPECTIVA ISOMETRICA", height=0.2)

    path = sheet.save(str(OUTPUT_DIR / "04_isometrica.dxf"))
    print(f"  Saved: {path}")


def test_cavaleira():
    """Generate a cavaleira perspective."""
    print("Generating cavaleira perspective...")

    sheet = TechnicalSheet("A3", scale="1:50")
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="PERSPECTIVA CAVALEIRA",
        drawing_number="05/05",
        author="Escora.AI",
        date="2026-04-13",
        scale_str="1:50",
        sheet_format="A3",
    ))

    origin = (0.05, 0.05)
    h = 2.80
    config = CavaleiraConfig.angle_45()

    draw_cavaleira_box(sheet, origin, 0, 0, 0, 7, 10, h, config=config)
    draw_cavaleira_box(sheet, origin, 0, 4.85, 0, 4, 0.15, h, config=config, draw_hidden=True)

    path = sheet.save(str(OUTPUT_DIR / "05_cavaleira.dxf"))
    print(f"  Saved: {path}")


def test_section():
    """Generate a building section (corte)."""
    print("Generating section (corte)...")

    sheet = TechnicalSheet("A2", scale="1:50")
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="CORTE A-A",
        drawing_number="02/05",
        author="Escora.AI",
        date="2026-04-13",
        scale_str="1:50",
        sheet_format="A2",
    ))

    # Wall data: (start, end, height, thickness)
    walls = [
        ((0, 0), (7, 0), 2.80, 0.15),     # South
        ((0, 10), (7, 10), 2.80, 0.15),    # North
        ((0, 0), (0, 10), 2.80, 0.15),     # West
        ((7, 0), (7, 10), 2.80, 0.15),     # East
        ((0, 5), (4, 5), 2.80, 0.15),      # Internal
        ((4, 0), (4, 10), 2.80, 0.15),     # Internal
    ]

    cut = SectionCut(
        label="A-A",
        start=(0, 5),
        end=(7, 5),
        direction="north",
    )

    generate_section_from_walls(
        sheet, walls, cut,
        origin=(0.05, 0.05),
        ceiling_height=2.80,
    )

    path = sheet.save(str(OUTPUT_DIR / "02_corte_aa.dxf"))
    print(f"  Saved: {path}")


def test_elevation():
    """Generate an elevation (fachada)."""
    print("Generating elevation (fachada)...")

    sheet = TechnicalSheet("A2", scale="1:50")
    sheet.add_title_block(TitleBlockInfo(
        project="RESIDENCIA UNIFAMILIAR",
        drawing_title="FACHADA FRONTAL (SUL)",
        drawing_number="03/05",
        author="Escora.AI",
        date="2026-04-13",
        scale_str="1:50",
        sheet_format="A2",
    ))

    walls = [
        ((0, 0), (7, 0), 2.80, 0.15),
    ]

    openings = [
        {"type": "door", "x": 1.0, "width": 0.80, "height": 2.10, "sill_height": 0},
        {"type": "window", "x": 2.5, "width": 1.50, "height": 1.20, "sill_height": 1.00},
        {"type": "window", "x": 5.0, "width": 1.20, "height": 1.00, "sill_height": 1.20},
    ]

    draw_elevation(
        sheet, walls, openings,
        origin=(0.05, 0.05),
        direction="south",
        label="FACHADA FRONTAL (SUL)",
    )

    # Dimension: total width
    sheet.add_dimension((0.05, 0.0), (7.05, 0.0), offset=-0.8)

    # Dimension: height
    sheet.add_dimension((0.05, 0.05), (0.05, 2.85), offset=-0.8, angle=90)

    path = sheet.save(str(OUTPUT_DIR / "03_fachada_sul.dxf"))
    print(f"  Saved: {path}")


def main():
    print("=" * 60)
    print("Technical Drawing Engine — NBR Compliance Test")
    print("=" * 60)
    print()

    test_floor_plan()
    test_section()
    test_elevation()
    test_isometric()
    test_cavaleira()

    print()
    print(f"All drawings saved to: {OUTPUT_DIR}")
    print("Open in AutoCAD, LibreCAD, or any DXF viewer to inspect.")


if __name__ == "__main__":
    main()
