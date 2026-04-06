"""DXF output generator — creates a clean structural plan with shore positions.

Two modes:
- overlay: adds shore layers onto the original DXF (preserves all input layers)
- clean: creates a new DXF with only structural elements + shores (like CVS-COB-escoras.dxf)

Layer structure (matches run_cvs_cob.py style):
- PILARES (red):        pillar outlines as rectangles
- VIGAS (blue):         beam outlines as rectangles (not just axis lines)
- LAJES (white):        slab polygon outlines
- ESCORAS_VIGAS (magenta): beam shore positions as circles
- ESCORAS_LAJES (green):   slab shore positions as squares
- TEXTO (gray):         element name labels
- INFO (cyan):          shore count info per slab
"""

import ezdxf
import logging
from pathlib import Path
from typing import List, Optional

from src.models.calculation_models import CalculationResult
from src.models.pipeline_models import ClassifiedElement, ElementType

logger = logging.getLogger(__name__)

# Shore symbol sizes (matching run_cvs_cob.py)
BEAM_SHORE_RADIUS = 0.05     # m — circle radius for beam shores
SLAB_SHORE_HALF = 0.05       # m — half-side of square for slab shores
TEXT_HEIGHT = 0.10            # m

# AutoCAD color indices
COLOR_PILLARS = 1       # Red
COLOR_BEAMS = 5         # Blue
COLOR_SLABS = 7         # White
COLOR_BEAM_SHORES = 6   # Magenta
COLOR_SLAB_SHORES = 3   # Green
COLOR_TEXT = 8           # Gray
COLOR_INFO = 4           # Cyan


def generate_dxf(
    input_path: str,
    calc: CalculationResult,
    output_path: str,
    elements: Optional[List[ClassifiedElement]] = None,
    mode: str = "overlay",
) -> str:
    """Generate DXF with shore positions.

    Args:
        input_path: Path to the original DXF file.
        calc: CalculationResult with shore positions.
        output_path: Where to save the output DXF.
        elements: All classified elements (for clean mode pillars/beams).
        mode: "overlay" (add to original) or "clean" (new DXF, structural only).

    Returns:
        Path to the saved DXF file.
    """
    if mode == "clean":
        doc = ezdxf.new("R2010")
    else:
        doc = ezdxf.readfile(input_path)
        # Upgrade old DXF versions to support LWPOLYLINE
        if doc.dxfversion < "AC1015":  # < R2000
            doc.dxfversion = "AC1015"

    msp = doc.modelspace()

    # Create layers
    if "PILARES" not in doc.layers:
        doc.layers.add("PILARES", color=COLOR_PILLARS)
    if "VIGAS" not in doc.layers:
        doc.layers.add("VIGAS", color=COLOR_BEAMS)
    if "LAJES" not in doc.layers:
        doc.layers.add("LAJES", color=COLOR_SLABS)
    if "ESCORAS_VIGAS" not in doc.layers:
        doc.layers.add("ESCORAS_VIGAS", color=COLOR_BEAM_SHORES)
    if "ESCORAS_LAJES" not in doc.layers:
        doc.layers.add("ESCORAS_LAJES", color=COLOR_SLAB_SHORES)
    if "TEXTO" not in doc.layers:
        doc.layers.add("TEXTO", color=COLOR_TEXT)
    if "INFO" not in doc.layers:
        doc.layers.add("INFO", color=COLOR_INFO)

    beam_shore_count = 0
    slab_shore_count = 0

    # Draw structural elements only in clean mode — overlay already has them
    if elements and mode == "clean":
        _draw_pillars(msp, [e for e in elements if e.element_type == ElementType.PILLAR])
        _draw_beams(msp, [e for e in elements if e.element_type == ElementType.BEAM])

    # Draw beam shores — circles (magenta)
    for br in calc.beam_results:
        beam = br.beam

        # Draw beam outline if not already drawn from elements
        if not elements and len(beam.geometry) >= 2:
            _draw_beam_rect(msp, beam)

        for s in br.shores:
            msp.add_circle(
                center=(s.x, s.y),
                radius=BEAM_SHORE_RADIUS,
                dxfattribs={"layer": "ESCORAS_VIGAS"},
            )
            beam_shore_count += 1

    # Draw slab shores — squares (green) + slab outlines
    for sr in calc.slab_results:
        # Slab outline
        if hasattr(sr.polygon, "exterior"):
            coords = list(sr.polygon.exterior.coords)
            msp.add_lwpolyline(
                [(x, y) for x, y in coords],
                close=True,
                dxfattribs={"layer": "LAJES"},
            )

        # Shore positions as 10x10cm squares
        for s in sr.shores:
            _draw_slab_shore(msp, s.x, s.y)
            slab_shore_count += 1

        # Info label at slab center
        if hasattr(sr.polygon, "centroid"):
            cx = sr.polygon.centroid.x
            cy = sr.polygon.centroid.y
            info = f"({len(sr.shores)} esc)"
            msp.add_text(
                info,
                height=TEXT_HEIGHT * 0.8,
                dxfattribs={"layer": "INFO"},
            ).set_placement((cx - 0.3, cy))

    # Save
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out))

    total = beam_shore_count + slab_shore_count
    logger.info(
        f"DXF saved: {out} ({beam_shore_count} beam shores, "
        f"{slab_shore_count} slab shores, {total} total)"
    )
    return str(out)


def _draw_pillars(msp, pillars: List[ClassifiedElement]):
    """Draw pillar outlines as rectangles + name labels."""
    for p in pillars:
        if not p.geometry:
            continue
        cx, cy = p.geometry[0]
        w = p.section_width_m or 0.20
        d = p.section_height_m or 0.20
        hw, hd = w / 2, d / 2

        msp.add_lwpolyline(
            [(cx - hw, cy - hd), (cx + hw, cy - hd),
             (cx + hw, cy + hd), (cx - hw, cy + hd)],
            close=True,
            dxfattribs={"layer": "PILARES"},
        )
        if p.name:
            msp.add_text(
                p.name,
                height=TEXT_HEIGHT,
                dxfattribs={"layer": "TEXTO"},
            ).set_placement((cx - 0.12, cy + hd + 0.05))


def _draw_beams(msp, beams: List[ClassifiedElement]):
    """Draw beam outlines as rectangles (not just axis lines)."""
    for b in beams:
        _draw_beam_rect(msp, b)


def _draw_beam_rect(msp, beam: ClassifiedElement):
    """Draw a single beam as a rectangle around its axis."""
    if len(beam.geometry) < 2:
        return
    start = beam.geometry[0]
    end = beam.geometry[1]
    w = beam.section_width_m or 0.14
    hw = w / 2

    dx = end[0] - start[0]
    dy = end[1] - start[1]

    if abs(dx) >= abs(dy):
        # Horizontal beam — width extends in Y
        msp.add_lwpolyline(
            [(start[0], start[1] - hw), (end[0], end[1] - hw),
             (end[0], end[1] + hw), (start[0], start[1] + hw)],
            close=True,
            dxfattribs={"layer": "VIGAS"},
        )
    else:
        # Vertical beam — width extends in X
        msp.add_lwpolyline(
            [(start[0] - hw, start[1]), (start[0] + hw, start[1]),
             (end[0] + hw, end[1]), (end[0] - hw, end[1])],
            close=True,
            dxfattribs={"layer": "VIGAS"},
        )

    # Beam name label
    mid_x = (start[0] + end[0]) / 2
    mid_y = (start[1] + end[1]) / 2
    label = beam.name or ""
    if label:
        msp.add_text(
            label,
            height=TEXT_HEIGHT,
            dxfattribs={"layer": "TEXTO"},
        ).set_placement((mid_x - 0.15, mid_y + hw + 0.05))


def _draw_slab_shore(msp, x: float, y: float):
    """Draw a slab shore symbol as a 10x10cm square."""
    s = SLAB_SHORE_HALF
    msp.add_lwpolyline(
        [(x - s, y - s), (x + s, y - s),
         (x + s, y + s), (x - s, y + s)],
        close=True,
        dxfattribs={"layer": "ESCORAS_LAJES"},
    )
