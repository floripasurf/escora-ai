"""NBR standards constants for technical drawing.

Consolidates all ABNT/NBR rules into typed constants used by the drawing engine.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional


# ---------------------------------------------------------------------------
# NBR 10068 — Sheet Formats
# ---------------------------------------------------------------------------

class SheetFormat(Enum):
    """Standard sheet sizes (mm)."""
    A0 = (841, 1189)
    A1 = (594, 841)
    A2 = (420, 594)
    A3 = (297, 420)
    A4 = (210, 297)

    @property
    def width_mm(self) -> int:
        return self.value[0]

    @property
    def height_mm(self) -> int:
        return self.value[1]

    @property
    def margin_left_mm(self) -> int:
        """Left margin — 25mm for all formats (filing margin)."""
        return 25

    @property
    def margin_other_mm(self) -> int:
        """Top/right/bottom margins."""
        return 10 if self != SheetFormat.A4 else 7

    @property
    def legend_width_mm(self) -> int:
        """Title block width."""
        return 175 if self in (SheetFormat.A0, SheetFormat.A1) else 178

    @property
    def drawable_width_mm(self) -> float:
        return self.width_mm - self.margin_left_mm - self.margin_other_mm

    @property
    def drawable_height_mm(self) -> float:
        return self.height_mm - 2 * self.margin_other_mm


# ---------------------------------------------------------------------------
# NBR 8403 — Line Types
# ---------------------------------------------------------------------------

class LineType(Enum):
    """Standard line types per NBR 8403."""
    # (name, description, pattern_mm, is_wide)
    A = ("CONTINUOUS", "Visible contours and edges", [], True)
    B = ("CONTINUOUS_NARROW", "Dimension lines, hatching, leaders", [], False)
    C = ("FREEHAND", "Rupture/break lines", [], False)
    E = ("DASHED", "Hidden edges", [6, 2], True)
    F = ("DASHED_NARROW", "Hidden edges (narrow)", [6, 2], False)
    G = ("DASHDOT", "Centerlines, symmetry axes", [12, 2, 2, 2], False)
    H = ("DASHDOT_WIDE", "Cutting planes", [12, 2, 2, 2], True)
    K = ("DASHDOTDOT", "Adjacent parts, alternate positions", [12, 2, 2, 2, 2, 2], False)

    @property
    def ezdxf_name(self) -> str:
        return self.value[0]

    @property
    def description(self) -> str:
        return self.value[1]

    @property
    def pattern(self) -> List[float]:
        return self.value[2]

    @property
    def is_wide(self) -> bool:
        return self.value[3]


# Standard line width series (mm) — NBR 8403
LINE_WIDTHS_MM = [0.13, 0.18, 0.25, 0.35, 0.50, 0.70, 1.00, 1.40, 2.00]

# Line width presets per drawing scale
LINE_WIDTH_PRESETS = {
    "1:1":   {"wide": 0.50, "narrow": 0.25},
    "1:2":   {"wide": 0.50, "narrow": 0.25},
    "1:5":   {"wide": 0.50, "narrow": 0.25},
    "1:10":  {"wide": 0.50, "narrow": 0.25},
    "1:20":  {"wide": 0.50, "narrow": 0.25},
    "1:25":  {"wide": 0.50, "narrow": 0.25},
    "1:50":  {"wide": 0.70, "narrow": 0.35},
    "1:100": {"wide": 0.70, "narrow": 0.35},
    "1:200": {"wide": 0.50, "narrow": 0.25},
    "1:500": {"wide": 0.35, "narrow": 0.18},
}

# Line priority order (higher priority drawn on top)
LINE_PRIORITY = [
    LineType.A,  # Visible contours (highest)
    LineType.E,  # Hidden edges
    LineType.H,  # Cutting planes
    LineType.G,  # Centerlines
    LineType.B,  # Dimension lines (lowest)
]

# ezdxf lineweight values (in 1/100 mm)
def mm_to_lineweight(mm: float) -> int:
    """Convert mm to ezdxf lineweight (nearest standard value)."""
    standard = [13, 18, 25, 35, 50, 70, 100, 140, 200]
    target = int(mm * 100)
    return min(standard, key=lambda x: abs(x - target))


# ---------------------------------------------------------------------------
# NBR 8196 — Scales
# ---------------------------------------------------------------------------

class Scale:
    """Drawing scale with real<->paper conversion."""

    # Standard scales per NBR 8196
    REDUCTION = ["1:2", "1:5", "1:10", "1:20", "1:25", "1:50",
                 "1:100", "1:200", "1:500", "1:1000"]
    NATURAL = ["1:1"]
    AMPLIFICATION = ["2:1", "5:1", "10:1", "20:1", "50:1"]

    def __init__(self, scale_str: str):
        parts = scale_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid scale format: {scale_str}")
        self.numerator = int(parts[0])
        self.denominator = int(parts[1])
        self._str = scale_str

    @property
    def factor(self) -> float:
        """Paper size / real size."""
        return self.numerator / self.denominator

    def real_to_paper(self, real_mm: float) -> float:
        """Convert real dimension to paper dimension."""
        return real_mm * self.factor

    def paper_to_real(self, paper_mm: float) -> float:
        """Convert paper dimension to real dimension."""
        return paper_mm / self.factor

    @property
    def is_reduction(self) -> bool:
        return self.factor < 1.0

    @property
    def is_amplification(self) -> bool:
        return self.factor > 1.0

    @property
    def label(self) -> str:
        return f"ESCALA {self._str}"

    def text_height_mm(self, target_paper_height_mm: float = 3.5) -> float:
        """Text height in model space to appear at target size on paper."""
        return target_paper_height_mm / self.factor

    def __str__(self) -> str:
        return self._str

    def __repr__(self) -> str:
        return f"Scale('{self._str}')"


# ---------------------------------------------------------------------------
# NBR 8402 — Lettering
# ---------------------------------------------------------------------------

@dataclass
class LetteringStyle:
    """Text style per NBR 8402."""
    height_mm: float  # h — base height
    is_inclined: bool = False  # False=vertical, True=15 degrees

    @property
    def uppercase_h(self) -> float:
        return self.height_mm

    @property
    def lowercase_h(self) -> float:
        return self.height_mm * 0.7

    @property
    def spacing(self) -> float:
        return self.height_mm * 0.2

    @property
    def baseline_spacing(self) -> float:
        return self.height_mm * 1.4

    @property
    def word_spacing(self) -> float:
        return self.height_mm * 0.6

    @property
    def line_width(self) -> float:
        return self.height_mm * 0.1

    @property
    def oblique_angle(self) -> float:
        """Angle in degrees for ezdxf (0=vertical, 15=inclined)."""
        return 15.0 if self.is_inclined else 0.0


# Standard text heights (mm)
TEXT_HEIGHTS_MM = [2.5, 3.5, 5.0, 7.0, 10.0, 14.0, 20.0]


# ---------------------------------------------------------------------------
# NBR 10126 — Dimensioning (Cotagem)
# ---------------------------------------------------------------------------

class DimensionMethod(Enum):
    """Dimension reading methods."""
    METHOD_1 = "parallel"   # Dimensions parallel to dimension line (ABNT default)
    METHOD_2 = "horizontal"  # All dimensions read from bottom


class DimensionTerminator(Enum):
    """Dimension line terminators."""
    ARROW = "arrow"          # 15-degree filled arrowhead
    OBLIQUE = "oblique"      # 45-degree oblique stroke
    DOT = "dot"              # Filled dot


@dataclass
class DimensionRules:
    """NBR 10126 dimensioning rules."""
    method: DimensionMethod = DimensionMethod.METHOD_1
    terminator: DimensionTerminator = DimensionTerminator.ARROW
    arrow_angle_deg: float = 15.0
    oblique_angle_deg: float = 45.0
    extension_gap_mm: float = 1.0      # Gap between object and extension line
    extension_overshoot_mm: float = 2.0  # Extension past dimension line
    text_gap_mm: float = 1.0           # Gap between dimension line and text
    min_spacing_mm: float = 7.0        # Min spacing between parallel dim lines
    first_dim_offset_mm: float = 10.0  # Distance of first dim line from object

    # Symbols
    DIAMETER = "\u2300"  # ⌀
    RADIUS = "R"
    SQUARE = "\u25A1"    # □
    SPHERICAL_D = "ESF \u2300"
    SPHERICAL_R = "ESF R"


# ---------------------------------------------------------------------------
# NBR 12298 — Hatching Patterns
# ---------------------------------------------------------------------------

class HatchMaterial(Enum):
    """Standard hatch patterns per material (NBR 12298)."""
    METAL = ("ANSI31", 45.0, 3.0)          # Diagonal lines
    CONCRETE = ("AR-CONC", 45.0, 5.0)      # Dots + triangles
    WOOD_ALONG = ("AR-HBONE", 0.0, 5.0)    # Along grain
    WOOD_ACROSS = ("AR-HBONE", 90.0, 5.0)  # Across grain
    BRICK = ("AR-BRSTD", 0.0, 5.0)         # Brick pattern
    STONE = ("AR-RSTO", 0.0, 5.0)          # Rubble stone
    SAND = ("AR-SAND", 0.0, 3.0)           # Dots
    EARTH = ("EARTH", 45.0, 3.0)           # Earth fill
    INSULATION = ("INSUL", 0.0, 5.0)       # Insulation
    GLASS = ("GLASS", 45.0, 3.0)           # Glass
    GENERIC = ("ANSI31", 45.0, 3.0)        # Default 45-degree lines

    @property
    def pattern_name(self) -> str:
        return self.value[0]

    @property
    def angle_deg(self) -> float:
        return self.value[1]

    @property
    def scale(self) -> float:
        return self.value[2]


# Hatching rules
HATCH_RULES = {
    "angle_deg": 45.0,
    "adjacent_different": True,        # Adjacent parts must differ in angle/spacing
    "large_area_border_only": True,    # Large areas hatched only at borders
    "ribs_not_hatched": True,          # Ribs/nervures NOT hatched longitudinally
    "bolts_never_hatched": True,       # Bolts/pins/rivets never hatched
    "shafts_never_hatched": True,      # Shafts shown as external view
}


# ---------------------------------------------------------------------------
# NBR 10067 — Projection System
# ---------------------------------------------------------------------------

class ProjectionSystem(Enum):
    """Orthographic projection system."""
    FIRST_DIEDRO = 1   # European/ISO/ABNT — object between observer and plane
    THIRD_DIEDRO = 3   # American/ANSI — plane between observer and object


@dataclass
class ViewArrangement:
    """View positions relative to frontal view (VF) for 1st diedro."""
    # 1st Diedro: VS below, VI above, VLE right, VLD left
    # 3rd Diedro: VS above, VI below, VLE left, VLD right
    system: ProjectionSystem = ProjectionSystem.FIRST_DIEDRO

    def view_position(self, view_name: str) -> Tuple[int, int]:
        """Return (col_offset, row_offset) relative to VF at (0,0).

        Positive x = right, positive y = up.
        """
        if self.system == ProjectionSystem.FIRST_DIEDRO:
            positions = {
                "VF": (0, 0),
                "VS": (0, -1),    # Superior below frontal
                "VI": (0, 1),     # Inferior above frontal
                "VLD": (-1, 0),   # Lateral direita to left
                "VLE": (1, 0),    # Lateral esquerda to right
                "VP": (2, 0),     # Posterior far right
            }
        else:  # 3rd diedro
            positions = {
                "VF": (0, 0),
                "VS": (0, 1),
                "VI": (0, -1),
                "VLD": (1, 0),
                "VLE": (-1, 0),
                "VP": (-2, 0),
            }
        return positions.get(view_name, (0, 0))


# ---------------------------------------------------------------------------
# Section/Cut types
# ---------------------------------------------------------------------------

class SectionType(Enum):
    """Types of sections (cortes) per NBR standards."""
    FULL = "pleno"           # Full section through entire object
    HALF = "meio_corte"      # Half section (symmetric parts)
    OFFSET = "em_desvio"     # Offset cutting plane
    PARTIAL = "parcial"      # Local/partial section
    REVOLVED = "rebatido"    # Revolved section (rotated 90 in place)


# ---------------------------------------------------------------------------
# AutoCAD Color Index — semantic mapping
# ---------------------------------------------------------------------------

ACI_COLORS = {
    "red": 1,
    "yellow": 2,
    "green": 3,
    "cyan": 4,
    "blue": 5,
    "magenta": 6,
    "white": 7,
    "gray": 8,
    "light_gray": 9,
}


# ---------------------------------------------------------------------------
# NBR class — facade
# ---------------------------------------------------------------------------

class NBR:
    """Facade for all NBR standard constants."""

    # Formats
    SheetFormat = SheetFormat

    # Lines
    LineType = LineType
    LINE_WIDTHS = LINE_WIDTHS_MM
    LINE_PRESETS = LINE_WIDTH_PRESETS

    # Scales
    Scale = Scale

    # Text
    LetteringStyle = LetteringStyle
    TEXT_HEIGHTS = TEXT_HEIGHTS_MM

    # Dimensions
    DimensionMethod = DimensionMethod
    DimensionTerminator = DimensionTerminator
    DimensionRules = DimensionRules

    # Hatching
    HatchMaterial = HatchMaterial
    HATCH_RULES = HATCH_RULES

    # Projections
    ProjectionSystem = ProjectionSystem
    ViewArrangement = ViewArrangement
    SectionType = SectionType

    # Colors
    COLORS = ACI_COLORS
