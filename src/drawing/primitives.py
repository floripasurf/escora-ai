"""Drawing primitives — NBR-compliant dimension, hatch, and annotation generators.

All primitives operate in model space (meters) and respect NBR standards
for line types, text height, arrow styles, and hatching patterns.
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Sequence

import ezdxf
from ezdxf.entities import DXFGraphic
from ezdxf.math import Vec2

from .nbr import (
    DimensionMethod, DimensionTerminator, DimensionRules,
    HatchMaterial, LetteringStyle, LineType, Scale,
    mm_to_lineweight,
)

Point2D = Tuple[float, float]


# ---------------------------------------------------------------------------
# Dimension Style (NBR 10126)
# ---------------------------------------------------------------------------

@dataclass
class DimensionStyle:
    """Configuration for NBR 10126-compliant dimensions."""
    rules: DimensionRules = field(default_factory=DimensionRules)
    scale: Scale = field(default_factory=lambda: Scale("1:50"))
    text_height_mm: float = 3.5
    layer: str = "COT"
    color: int = 3  # Green

    @property
    def text_height_model(self) -> float:
        """Text height in model units (meters)."""
        return self.scale.text_height_mm(self.text_height_mm) / 1000.0

    @property
    def arrow_size_model(self) -> float:
        return self.text_height_model * 1.5

    @property
    def extension_gap_model(self) -> float:
        return self.rules.extension_gap_mm / 1000.0 / self.scale.factor

    @property
    def extension_overshoot_model(self) -> float:
        return self.rules.extension_overshoot_mm / 1000.0 / self.scale.factor

    @property
    def first_offset_model(self) -> float:
        return self.rules.first_dim_offset_mm / 1000.0 / self.scale.factor

    @property
    def min_spacing_model(self) -> float:
        return self.rules.min_spacing_mm / 1000.0 / self.scale.factor


def setup_dim_style(doc: ezdxf.document.Drawing, style: DimensionStyle) -> str:
    """Register an NBR-compliant dimension style in the DXF document."""
    name = "NBR_DIM"
    if name in doc.dimstyles:
        return name

    ds = doc.dimstyles.new(name)

    # Text
    ds.dxf.dimtxt = style.text_height_model
    ds.dxf.dimtad = 1  # Text above dimension line (Method 1)
    ds.dxf.dimjust = 0  # Center justified

    # Arrows
    if style.rules.terminator == DimensionTerminator.ARROW:
        ds.dxf.dimasz = style.arrow_size_model
        # Default closed filled arrows
    elif style.rules.terminator == DimensionTerminator.OBLIQUE:
        ds.dxf.dimasz = style.arrow_size_model
        ds.dxf.dimblk = "OBLIQUE"
    elif style.rules.terminator == DimensionTerminator.DOT:
        ds.dxf.dimasz = style.arrow_size_model * 0.5
        ds.dxf.dimblk = "DOT"

    # Extension lines
    ds.dxf.dimexo = style.extension_gap_model
    ds.dxf.dimexe = style.extension_overshoot_model

    # Tolerances and precision
    ds.dxf.dimdec = 2   # 2 decimal places
    ds.dxf.dimdsep = 44  # Comma as decimal separator (pt-BR)

    # Color and layer
    ds.dxf.dimclrd = style.color  # Dimension line color
    ds.dxf.dimclre = style.color  # Extension line color
    ds.dxf.dimclrt = style.color  # Text color

    return name


# ---------------------------------------------------------------------------
# Linear Dimension (NBR 10126)
# ---------------------------------------------------------------------------

def add_linear_dimension(
    msp,
    p1: Point2D,
    p2: Point2D,
    offset: float,
    text: Optional[str] = None,
    angle: float = 0.0,
    style_name: str = "NBR_DIM",
    layer: str = "COT",
) -> None:
    """Add a linear dimension between two points.

    Args:
        msp: ezdxf modelspace
        p1: First definition point
        p2: Second definition point
        offset: Distance of dimension line from object (positive = up/right)
        text: Override text (None = auto-calculate)
        angle: Rotation angle in degrees (0=horizontal, 90=vertical)
        style_name: Dimension style name
        layer: Target layer
    """
    # Calculate dimension line position
    override = {}
    if text:
        override["dimtxt"] = text

    if abs(angle) < 1:  # Horizontal
        dim_point = (p1[0], p1[1] + offset)
        dim = msp.add_linear_dim(
            base=dim_point, p1=p1, p2=p2, angle=0,
            dimstyle=style_name, override=override,
        )
    elif abs(angle - 90) < 1:  # Vertical
        dim_point = (p1[0] + offset, p1[1])
        dim = msp.add_linear_dim(
            base=dim_point, p1=p1, p2=p2, angle=90,
            dimstyle=style_name, override=override,
        )
    else:  # Angled
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.sqrt(dx**2 + dy**2)
        nx = -dy / length * offset
        ny = dx / length * offset
        dim_point = (p1[0] + nx, p1[1] + ny)
        dim = msp.add_linear_dim(
            base=dim_point, p1=p1, p2=p2, angle=angle,
            dimstyle=style_name, override=override,
        )

    dim.render()


def add_aligned_dimension(
    msp,
    p1: Point2D,
    p2: Point2D,
    offset: float,
    text: Optional[str] = None,
    style_name: str = "NBR_DIM",
    layer: str = "COT",
) -> None:
    """Add an aligned dimension (parallel to the measured line)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.sqrt(dx**2 + dy**2)
    if length < 1e-6:
        return
    nx = -dy / length * offset
    ny = dx / length * offset
    dim_point = (p1[0] + nx, p1[1] + ny)

    dim = msp.add_aligned_dim(
        p1=p1,
        p2=p2,
        distance=offset,
        dimstyle=style_name,
    )
    dim.render()


def add_chain_dimensions(
    msp,
    points: List[Point2D],
    offset: float,
    angle: float = 0.0,
    style_name: str = "NBR_DIM",
    layer: str = "COT",
    add_total: bool = True,
    total_offset_factor: float = 2.0,
) -> None:
    """Add chain (serial) dimensions through a sequence of points.

    NBR 10126: cotagem em serie — sequential dimensions sharing extension lines.
    Optionally adds a total dimension further from the object.
    """
    for i in range(len(points) - 1):
        add_linear_dimension(
            msp, points[i], points[i + 1],
            offset=offset, angle=angle,
            style_name=style_name, layer=layer,
        )

    if add_total and len(points) >= 3:
        add_linear_dimension(
            msp, points[0], points[-1],
            offset=offset * total_offset_factor,
            angle=angle,
            style_name=style_name, layer=layer,
        )


def add_radius_dimension(
    msp,
    center: Point2D,
    radius: float,
    angle_deg: float = 45.0,
    style_name: str = "NBR_DIM",
    layer: str = "COT",
) -> None:
    """Add a radius dimension (R prefix per NBR 10126)."""
    rad = math.radians(angle_deg)
    p_on_arc = (
        center[0] + radius * math.cos(rad),
        center[1] + radius * math.sin(rad),
    )
    dim = msp.add_radius_dim(
        center=center,
        radius=radius,
        angle=angle_deg,
        dimstyle=style_name,
    )
    dim.render()


def add_diameter_dimension(
    msp,
    center: Point2D,
    radius: float,
    angle_deg: float = 45.0,
    style_name: str = "NBR_DIM",
    layer: str = "COT",
) -> None:
    """Add a diameter dimension (symbol prefix per NBR 10126)."""
    dim = msp.add_diameter_dim(
        center=center,
        radius=radius,
        angle=angle_deg,
        dimstyle=style_name,
    )
    dim.render()


# ---------------------------------------------------------------------------
# Hatching (NBR 12298)
# ---------------------------------------------------------------------------

@dataclass
class HatchPattern:
    """Hatch configuration per NBR 12298."""
    material: HatchMaterial = HatchMaterial.GENERIC
    angle_deg: float = 45.0
    scale: float = 1.0
    layer: str = "HATCH"
    color: int = 251  # Light gray

    @classmethod
    def for_material(cls, material: HatchMaterial, **kwargs) -> "HatchPattern":
        return cls(
            material=material,
            angle_deg=material.angle_deg,
            scale=material.scale,
            **kwargs,
        )


def add_hatch(
    msp,
    boundary: List[Point2D],
    pattern: HatchPattern,
) -> None:
    """Add a hatch fill to a closed boundary.

    Args:
        msp: ezdxf modelspace
        boundary: List of (x,y) points forming closed boundary
        pattern: Hatch configuration
    """
    hatch = msp.add_hatch(
        color=pattern.color,
        dxfattribs={"layer": pattern.layer},
    )
    hatch.set_pattern_fill(
        pattern.material.pattern_name,
        scale=pattern.scale,
        angle=pattern.angle_deg,
    )
    hatch.paths.add_polyline_path(
        [(p[0], p[1]) for p in boundary],
        is_closed=True,
    )


def add_section_hatch(
    msp,
    boundary: List[Point2D],
    material: HatchMaterial = HatchMaterial.GENERIC,
    layer: str = "HATCH-CORTE",
    section_index: int = 0,
) -> None:
    """Add section hatching with automatic angle rotation for adjacent parts.

    Per NBR 12298: adjacent parts in sections must have different hatch
    angle or spacing. section_index controls the rotation.
    """
    base_angle = material.angle_deg
    # Rotate by 90 degrees for alternating adjacent parts
    angle = base_angle + (90.0 * (section_index % 2))

    pattern = HatchPattern(
        material=material,
        angle_deg=angle,
        scale=material.scale * (1.0 + 0.3 * (section_index % 3)),
        layer=layer,
    )
    add_hatch(msp, boundary, pattern)


# ---------------------------------------------------------------------------
# Text / Labels (NBR 8402)
# ---------------------------------------------------------------------------

def add_text(
    msp,
    position: Point2D,
    text: str,
    height: float,
    layer: str = "TEXTO",
    color: int = 7,
    rotation: float = 0.0,
    halign: str = "LEFT",
    valign: str = "BOTTOM",
    style: str = "Standard",
) -> None:
    """Add NBR 8402-compliant text."""
    align_map = {
        ("LEFT", "BOTTOM"): ezdxf.enums.TextEntityAlignment.LEFT,
        ("CENTER", "BOTTOM"): ezdxf.enums.TextEntityAlignment.CENTER,
        ("RIGHT", "BOTTOM"): ezdxf.enums.TextEntityAlignment.RIGHT,
        ("LEFT", "MIDDLE"): ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT,
        ("CENTER", "MIDDLE"): ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
        ("RIGHT", "MIDDLE"): ezdxf.enums.TextEntityAlignment.MIDDLE_RIGHT,
        ("LEFT", "TOP"): ezdxf.enums.TextEntityAlignment.TOP_LEFT,
        ("CENTER", "TOP"): ezdxf.enums.TextEntityAlignment.TOP_CENTER,
        ("RIGHT", "TOP"): ezdxf.enums.TextEntityAlignment.TOP_RIGHT,
    }
    alignment = align_map.get((halign, valign), ezdxf.enums.TextEntityAlignment.LEFT)

    msp.add_text(
        text,
        height=height,
        rotation=rotation,
        dxfattribs={
            "layer": layer,
            "color": color,
            "style": style,
        },
    ).set_placement(position, align=alignment)


def add_room_label(
    msp,
    center: Point2D,
    name: str,
    area_m2: float,
    text_height: float = 0.15,
    layer: str = "TEXTO",
) -> None:
    """Add room label with name and area (architectural convention)."""
    add_text(
        msp, (center[0], center[1] + text_height * 0.8),
        name.upper(), text_height,
        layer=layer, halign="CENTER", valign="MIDDLE",
    )
    add_text(
        msp, (center[0], center[1] - text_height * 0.8),
        f"A={area_m2:.2f}m\u00B2", text_height * 0.7,
        layer=layer, halign="CENTER", valign="MIDDLE",
        color=8,
    )


# ---------------------------------------------------------------------------
# Leader / Callout
# ---------------------------------------------------------------------------

def add_leader(
    msp,
    target: Point2D,
    text_pos: Point2D,
    text: str,
    text_height: float = 0.10,
    layer: str = "COT",
    color: int = 3,
) -> None:
    """Add a leader line with text annotation."""
    # Leader line
    msp.add_line(
        target, text_pos,
        dxfattribs={"layer": layer, "color": color},
    )
    # Arrow at target
    dx = text_pos[0] - target[0]
    dy = text_pos[1] - target[1]
    length = math.sqrt(dx**2 + dy**2)
    if length > 0:
        arrow_len = text_height * 1.5
        ux, uy = dx / length, dy / length
        # Arrowhead as small triangle
        perp_x, perp_y = -uy, ux
        tip = target
        base1 = (tip[0] + ux * arrow_len + perp_x * arrow_len * 0.3,
                 tip[1] + uy * arrow_len + perp_y * arrow_len * 0.3)
        base2 = (tip[0] + ux * arrow_len - perp_x * arrow_len * 0.3,
                 tip[1] + uy * arrow_len - perp_y * arrow_len * 0.3)
        hatch = msp.add_hatch(color=color, dxfattribs={"layer": layer})
        hatch.paths.add_polyline_path([tip, base1, base2], is_closed=True)

    # Horizontal shelf line
    shelf_dir = 1 if text_pos[0] >= target[0] else -1
    shelf_end = (text_pos[0] + shelf_dir * len(text) * text_height * 0.6, text_pos[1])
    msp.add_line(
        text_pos, shelf_end,
        dxfattribs={"layer": layer, "color": color},
    )

    # Text above shelf
    add_text(
        msp, (text_pos[0], text_pos[1] + text_height * 0.3),
        text, text_height,
        layer=layer, color=color,
        halign="LEFT" if shelf_dir > 0 else "RIGHT",
    )


# ---------------------------------------------------------------------------
# Section Indicator (Cutting Plane)
# ---------------------------------------------------------------------------

def add_cutting_plane(
    msp,
    start: Point2D,
    end: Point2D,
    label: str = "A",
    layer: str = "CORTE",
    color: int = 1,
    arrow_size: float = 0.15,
) -> None:
    """Draw a cutting plane line with direction arrows and label.

    Line type H (dash-dot wide at ends) per NBR 8403.
    Arrows show viewing direction.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.sqrt(dx**2 + dy**2)
    if length < 1e-6:
        return

    ux, uy = dx / length, dy / length
    # Perpendicular direction for arrows (viewing direction)
    px, py = -uy, ux

    # Main cutting plane line
    msp.add_line(
        start, end,
        dxfattribs={
            "layer": layer,
            "color": color,
            "linetype": "DASHDOT",
        },
    )

    # Arrow at start
    arrow_tip_s = (start[0] + px * arrow_size * 2, start[1] + py * arrow_size * 2)
    msp.add_line(
        start, arrow_tip_s,
        dxfattribs={"layer": layer, "color": color},
    )

    # Arrow at end
    arrow_tip_e = (end[0] + px * arrow_size * 2, end[1] + py * arrow_size * 2)
    msp.add_line(
        end, arrow_tip_e,
        dxfattribs={"layer": layer, "color": color},
    )

    # Labels
    text_h = arrow_size * 1.2
    add_text(
        msp,
        (start[0] + px * arrow_size * 3, start[1] + py * arrow_size * 3),
        label, text_h, layer=layer, color=color,
        halign="CENTER", valign="MIDDLE",
    )
    add_text(
        msp,
        (end[0] + px * arrow_size * 3, end[1] + py * arrow_size * 3),
        label, text_h, layer=layer, color=color,
        halign="CENTER", valign="MIDDLE",
    )
