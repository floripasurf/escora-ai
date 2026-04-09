"""DXF output generator — creates a clean structural plan with shore positions.

Layer naming follows the **Orguel engineer convention** observed in real
locadora projects (input/orguel/*.dxf), so the engineer opening our output
sees the exact same layer tree they're already used to:

    ESC310_Viga, ESC360_Viga, ESC450_Viga       — beam shores by model
    ESC310_Laje, ESC360_Laje, ESC450_Laje       — slab shores by model
    TORRE_VIGA, TORRE_LAJE                      — towers under beams / slabs
    VM50_Viga, VM80_Viga, VM130_Viga            — distribution beams (when present)
    PILARES, VIGAS, LAJES                       — structural geometry
    Listamat                                    — material list / BOM table area
    TEXTO, INFO                                 — labels and metadata

Two modes:
- overlay: adds shore layers onto the original DXF (preserves all input layers)
- clean: creates a new DXF with only structural elements + shores
"""

import ezdxf
import logging
from pathlib import Path
from typing import List, Optional

from src.models.calculation_models import CalculationResult
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.shore import SupportType

logger = logging.getLogger(__name__)

# Shore symbol sizes
BEAM_SHORE_RADIUS = 0.05     # m — circle radius for beam shores
SLAB_SHORE_HALF = 0.05       # m — half-side of square for slab shores
TOWER_HALF = 0.10            # m — towers drawn larger than telescopic shores
TEXT_HEIGHT = 0.10            # m

# AutoCAD color indices for structural geometry
COLOR_PILLARS = 1       # Red
COLOR_BEAMS = 5         # Blue
COLOR_SLABS = 7         # White
COLOR_TEXT = 8          # Gray
COLOR_INFO = 4          # Cyan

# Color map calibrated on Orguel-authored DXFs (input/orguel/*.dxf).
# Falls back to a deterministic hash when an unknown model appears so layers
# always have *some* color and never collide with the "0" default.
ORGUEL_LAYER_COLORS = {
    "ESC310_Viga": 5,    "ESC310_Laje": 5,
    "ESC360_Viga": 96,   "ESC360_Laje": 96,
    "ESC450_Viga": 1,    "ESC450_Laje": 1,
    "ESC360-CRUZ": 96,   "ESC450-CRUZ": 1,
    "TORRE_VIGA": 7,     "TORRE_LAJE": 7,
    "VM50_Viga": 6,      "VM50_Laje": 6,
    "VM80_Viga": 1,      "VM80_Laje": 1,
    "VM130_Viga": 170,   "VM130_Laje": 170,
    "ALU14_Viga": 132,   "ALU14_Laje": 132,
    "Tirante": 82,       "Tirante_Viga": 5,
    "Trav-Pilar": 7,     "Listamat": 7,
}


def _layer_color(name: str) -> int:
    """Return the calibrated color for a known Orguel layer or a stable hash."""
    if name in ORGUEL_LAYER_COLORS:
        return ORGUEL_LAYER_COLORS[name]
    # Deterministic 1-255 (0 = ByBlock, never use)
    return (sum(ord(c) for c in name) % 254) + 1


def _ensure_layer(doc, name: str, color: Optional[int] = None) -> None:
    if name not in doc.layers:
        doc.layers.add(name, color=color if color is not None else _layer_color(name))


def _shore_layer_name(positioned_shore, target: str) -> str:
    """Map a PositionedShore + target ('Viga'|'Laje') to its Orguel layer.

    target='Viga' for shores under beams, 'Laje' for shores under slabs.
    Towers collapse to TORRE_VIGA / TORRE_LAJE regardless of model since
    that's how Orguel engineers organize them in real projects.
    """
    if getattr(positioned_shore, "support_type", None) == SupportType.TOWER:
        return f"TORRE_{target.upper()}"
    model_id = positioned_shore.shore.id  # e.g. "ESC310"
    return f"{model_id}_{target}"


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

    # Structural geometry layers (always present, Orguel uses these names too)
    _ensure_layer(doc, "PILARES", COLOR_PILLARS)
    _ensure_layer(doc, "VIGAS", COLOR_BEAMS)
    _ensure_layer(doc, "LAJES", COLOR_SLABS)
    _ensure_layer(doc, "TEXTO", COLOR_TEXT)
    _ensure_layer(doc, "INFO", COLOR_INFO)

    beam_shore_count = 0
    slab_shore_count = 0

    # Draw structural elements only in clean mode — overlay already has them
    if elements and mode == "clean":
        _draw_pillars(msp, [e for e in elements if e.element_type == ElementType.PILLAR])
        _draw_beams(msp, [e for e in elements if e.element_type == ElementType.BEAM])

    # Draw beam shores — Orguel naming: ESC{model}_Viga / TORRE_VIGA
    for br in calc.beam_results:
        beam = br.beam

        # Draw beam outline if not already drawn from elements
        if not elements and len(beam.geometry) >= 2:
            _draw_beam_rect(msp, beam)

        for s in br.shores:
            layer = _shore_layer_name(s, "Viga")
            _ensure_layer(doc, layer)
            is_tower = getattr(s, "support_type", None) == SupportType.TOWER
            if is_tower:
                _draw_tower_marker(msp, s.x, s.y, layer)
            else:
                msp.add_circle(
                    center=(s.x, s.y),
                    radius=BEAM_SHORE_RADIUS,
                    dxfattribs={"layer": layer},
                )
            beam_shore_count += 1

        # Distribution beam under this beam? Draw a thin line on VM*_Viga.
        for s in br.shores:
            db = getattr(s, "distribution_beam", None)
            if db is None:
                continue
            vm_layer = f"{db.id.split('-')[1] if '-' in db.id else db.id}_Viga"
            # Catalog ids look like "VD-VM130-410"; collapse to "VM130_Viga".
            if "VM" in db.id:
                vm_token = next((t for t in db.id.split("-") if t.startswith("VM")), db.id)
                vm_layer = f"{vm_token}_Viga"
            _ensure_layer(doc, vm_layer)

    # Draw slab shores — Orguel naming: ESC{model}_Laje / TORRE_LAJE
    for sr in calc.slab_results:
        # Slab outline
        if hasattr(sr.polygon, "exterior"):
            coords = list(sr.polygon.exterior.coords)
            msp.add_lwpolyline(
                [(x, y) for x, y in coords],
                close=True,
                dxfattribs={"layer": "LAJES"},
            )

        for s in sr.shores:
            layer = _shore_layer_name(s, "Laje")
            _ensure_layer(doc, layer)
            is_tower = getattr(s, "support_type", None) == SupportType.TOWER
            if is_tower:
                _draw_tower_marker(msp, s.x, s.y, layer)
            else:
                _draw_slab_shore(msp, s.x, s.y, layer)
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


def _draw_slab_shore(msp, x: float, y: float, layer: str):
    """Draw a slab shore symbol as a 10x10cm square on the given layer."""
    s = SLAB_SHORE_HALF
    msp.add_lwpolyline(
        [(x - s, y - s), (x + s, y - s),
         (x + s, y + s), (x - s, y + s)],
        close=True,
        dxfattribs={"layer": layer},
    )


def _draw_tower_marker(msp, x: float, y: float, layer: str):
    """Draw a tower footprint as a 20x20cm square with a diagonal cross.

    Mirrors the way Orguel engineers symbolize tower bases — a larger filled
    square with an X to distinguish it from telescopic shore circles.
    """
    s = TOWER_HALF
    msp.add_lwpolyline(
        [(x - s, y - s), (x + s, y - s),
         (x + s, y + s), (x - s, y + s)],
        close=True,
        dxfattribs={"layer": layer},
    )
    msp.add_line((x - s, y - s), (x + s, y + s), dxfattribs={"layer": layer})
    msp.add_line((x - s, y + s), (x + s, y - s), dxfattribs={"layer": layer})
