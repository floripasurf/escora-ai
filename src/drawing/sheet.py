"""Technical drawing sheet — format, margins, title block, layers, and DXF output.

Provides TechnicalSheet as the main entry point for creating NBR-compliant
technical drawings. Handles sheet setup, layer management, title block,
and delegates to primitives for actual geometry.
"""

import math
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import ezdxf

from .nbr import (
    SheetFormat, LineType, Scale, HatchMaterial, ProjectionSystem, ViewArrangement,
    mm_to_lineweight,
)
from .primitives import (
    DimensionStyle, HatchPattern, setup_dim_style,
    add_linear_dimension, add_chain_dimensions,
    add_radius_dimension, add_diameter_dimension,
    add_hatch, add_section_hatch, add_text, add_room_label,
    add_leader, add_cutting_plane,
)

logger = logging.getLogger(__name__)

Point2D = Tuple[float, float]


# ---------------------------------------------------------------------------
# Standard layer definitions
# ---------------------------------------------------------------------------

@dataclass
class LayerDef:
    """Layer definition with NBR-compliant properties."""
    name: str
    color: int
    lineweight: int  # 1/100 mm (ezdxf format)
    linetype: str = "Continuous"
    description: str = ""


# Default layer set for architectural drawings
ARCH_LAYERS: List[LayerDef] = [
    LayerDef("PAR-ESTRU", 7, 50, description="Structural walls"),
    LayerDef("PAR-VEDA", 253, 25, description="Non-structural walls"),
    LayerDef("ESQ-PORTA", 1, 25, description="Doors"),
    LayerDef("ESQ-JANELA", 5, 25, description="Windows"),
    LayerDef("COT", 3, 13, description="Dimensions"),
    LayerDef("TEXTO", 7, 18, description="Text and labels"),
    LayerDef("HATCH", 251, 13, description="Hatching"),
    LayerDef("HATCH-CORTE", 251, 13, description="Section hatching"),
    LayerDef("EIXO", 4, 13, "DASHDOT", "Center/axis lines"),
    LayerDef("OCULTA", 8, 25, "DASHED", "Hidden edges"),
    LayerDef("CORTE", 1, 35, "DASHDOT", "Cutting plane lines"),
    LayerDef("LEGENDA", 7, 25, description="Title block"),
    LayerDef("MARGEM", 7, 50, description="Sheet border/margin"),
    LayerDef("PROJ-DIEDRO", 8, 13, description="Projection symbol"),
]

# Default layer set for structural drawings
STRUCT_LAYERS: List[LayerDef] = [
    LayerDef("EST-PAREDE", 7, 50, description="Structural walls"),
    LayerDef("EST-CINTA", 3, 35, description="Tie beams"),
    LayerDef("EST-VERGA", 1, 35, description="Lintels"),
    LayerDef("EST-FUND", 6, 50, description="Foundations"),
    LayerDef("EST-PILAR", 1, 50, description="Columns"),
    LayerDef("EST-VIGA", 5, 50, description="Beams"),
    LayerDef("EST-LAJE", 4, 35, description="Slabs"),
    LayerDef("EST-ARM", 1, 18, description="Reinforcement"),
    LayerDef("COT", 3, 13, description="Dimensions"),
    LayerDef("TEXTO", 7, 18, description="Text"),
    LayerDef("HATCH-CORTE", 251, 13, description="Section hatching"),
    LayerDef("CORTE", 1, 35, "DASHDOT", "Cutting plane"),
    LayerDef("LEGENDA", 7, 25, description="Title block"),
    LayerDef("MARGEM", 7, 50, description="Sheet border"),
]


# ---------------------------------------------------------------------------
# Title Block (Carimbo / Legenda)
# ---------------------------------------------------------------------------

@dataclass
class TitleBlockInfo:
    """Information displayed in the title block (carimbo)."""
    project: str = ""
    drawing_title: str = ""
    drawing_number: str = ""
    author: str = ""
    responsible: str = ""
    crea_number: str = ""
    date: str = ""
    revision: str = "0"
    scale_str: str = "1:50"
    sheet_format: str = "A1"
    client: str = ""
    location: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# TechnicalSheet — main drawing class
# ---------------------------------------------------------------------------

class TechnicalSheet:
    """NBR-compliant technical drawing sheet.

    Usage:
        sheet = TechnicalSheet("A1", scale="1:50")
        sheet.add_title_block(project="Residencia", author="Eng. Silva")
        sheet.draw_wall((0,0), (5,0), thickness=0.15)
        sheet.add_dimension((0,0), (5,0), offset=-0.5)
        sheet.save("planta.dxf")
    """

    def __init__(
        self,
        format_name: str = "A1",
        scale: str = "1:50",
        projection: ProjectionSystem = ProjectionSystem.FIRST_DIEDRO,
        layer_set: str = "arch",
    ):
        self.format = SheetFormat[format_name]
        self.scale = Scale(scale)
        self.projection = projection
        self.view_arrangement = ViewArrangement(projection)

        # Create DXF document
        self.doc = ezdxf.new("R2010")
        self.msp = self.doc.modelspace()

        # Setup line types
        self._setup_linetypes()

        # Setup layers
        layers = ARCH_LAYERS if layer_set == "arch" else STRUCT_LAYERS
        for ldef in layers:
            self._ensure_layer(ldef)

        # Setup dimension style
        self.dim_style = DimensionStyle(scale=self.scale)
        self._dim_style_name = setup_dim_style(self.doc, self.dim_style)

        # Setup text style
        self._setup_text_style()

        # Drawing origin offset (for positioning within sheet)
        self.origin_x = 0.0
        self.origin_y = 0.0

        logger.info(
            f"TechnicalSheet created: {format_name} scale={scale} "
            f"projection={projection.name}"
        )

    def _setup_linetypes(self) -> None:
        """Register NBR 8403 line types in the DXF document."""
        lt_table = self.doc.linetypes
        if "DASHED" not in lt_table:
            lt_table.add(
                "DASHED",
                pattern=[10.0, 6.0, -2.0],
                description="Hidden edges __ __ __",
            )
        if "DASHDOT" not in lt_table:
            lt_table.add(
                "DASHDOT",
                pattern=[18.0, 12.0, -2.0, 0.5, -2.0],
                description="Center/axis _._._.",
            )
        if "DASHDOTDOT" not in lt_table:
            lt_table.add(
                "DASHDOTDOT",
                pattern=[24.0, 12.0, -2.0, 0.5, -2.0, 0.5, -2.0],
                description="Adjacent parts _.._.._..",
            )

    def _ensure_layer(self, ldef: LayerDef) -> None:
        """Create layer if not exists."""
        if ldef.name not in self.doc.layers:
            attrs = {
                "color": ldef.color,
                "lineweight": ldef.lineweight,
            }
            if ldef.linetype != "Continuous":
                attrs["linetype"] = ldef.linetype
            self.doc.layers.add(ldef.name, **attrs)

    def _setup_text_style(self) -> None:
        """Register NBR 8402 text style."""
        if "NBR" not in self.doc.styles:
            self.doc.styles.new("NBR", dxfattribs={
                "font": "isocpeur.shx",  # ISO technical font
                "width": 0.8,
            })

    def add_layer(
        self,
        name: str,
        color: int = 7,
        lineweight_mm: float = 0.25,
        linetype: str = "Continuous",
    ) -> None:
        """Add a custom layer."""
        ldef = LayerDef(
            name=name,
            color=color,
            lineweight=mm_to_lineweight(lineweight_mm),
            linetype=linetype,
        )
        self._ensure_layer(ldef)

    # -------------------------------------------------------------------
    # Sheet frame and title block
    # -------------------------------------------------------------------

    def draw_sheet_frame(self) -> None:
        """Draw sheet border and margins per NBR 10068.

        Draws in paper space coordinates (mm), scaled by 1/1000 to meters.
        """
        s = 1.0 / 1000.0  # mm to meters
        w = self.format.width_mm * s
        h = self.format.height_mm * s
        ml = self.format.margin_left_mm * s
        mo = self.format.margin_other_mm * s

        # Outer border
        border = [(0, 0), (w, 0), (w, h), (0, h), (0, 0)]
        self.msp.add_lwpolyline(
            border,
            dxfattribs={"layer": "MARGEM", "lineweight": 50},
        )

        # Inner margin
        margin = [
            (ml, mo), (w - mo, mo),
            (w - mo, h - mo), (ml, h - mo),
            (ml, mo),
        ]
        self.msp.add_lwpolyline(
            margin,
            dxfattribs={"layer": "MARGEM", "lineweight": 25},
        )

    def add_title_block(self, info: Optional[TitleBlockInfo] = None, **kwargs) -> None:
        """Draw title block (carimbo) per NBR 10582.

        Args:
            info: TitleBlockInfo instance, or pass fields as kwargs
        """
        if info is None:
            info = TitleBlockInfo(**kwargs)

        s = 1.0 / 1000.0
        w = self.format.width_mm * s
        h = self.format.height_mm * s
        mo = self.format.margin_other_mm * s
        lw = self.format.legend_width_mm * s
        lh = 50 * s  # Legend height ~50mm

        # Title block rectangle (bottom-right corner)
        x0 = w - mo - lw
        y0 = mo
        x1 = w - mo
        y1 = mo + lh

        layer = "LEGENDA"

        # Outer rectangle
        self.msp.add_lwpolyline(
            [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
            dxfattribs={"layer": layer, "lineweight": 35},
        )

        # Horizontal divisions
        row_h = lh / 5
        for i in range(1, 5):
            y = y0 + row_h * i
            self.msp.add_line(
                (x0, y), (x1, y),
                dxfattribs={"layer": layer},
            )

        # Vertical division (left 60% / right 40%)
        xm = x0 + lw * 0.6
        self.msp.add_line(
            (xm, y0), (xm, y0 + row_h * 3),
            dxfattribs={"layer": layer},
        )

        # Text entries
        th = 2.5 * s  # Text height
        th_title = 5.0 * s  # Title text height
        pad = 2 * s

        # Row 5 (top): Project name
        add_text(
            self.msp, (x0 + pad, y0 + row_h * 4 + pad),
            info.project.upper(), th_title,
            layer=layer, style="NBR",
        )

        # Row 4: Drawing title
        add_text(
            self.msp, (x0 + pad, y0 + row_h * 3 + pad),
            info.drawing_title, th,
            layer=layer, style="NBR",
        )

        # Row 3 left: Author
        add_text(
            self.msp, (x0 + pad, y0 + row_h * 2 + pad),
            f"RESP: {info.responsible or info.author}", th,
            layer=layer, style="NBR",
        )
        # Row 3 right: CREA
        if info.crea_number:
            add_text(
                self.msp, (xm + pad, y0 + row_h * 2 + pad),
                f"CREA: {info.crea_number}", th,
                layer=layer, style="NBR",
            )

        # Row 2 left: Date
        add_text(
            self.msp, (x0 + pad, y0 + row_h + pad),
            f"DATA: {info.date}", th,
            layer=layer, style="NBR",
        )
        # Row 2 right: Revision
        add_text(
            self.msp, (xm + pad, y0 + row_h + pad),
            f"REV: {info.revision}", th,
            layer=layer, style="NBR",
        )

        # Row 1 left: Scale
        add_text(
            self.msp, (x0 + pad, y0 + pad),
            f"ESCALA {info.scale_str}", th,
            layer=layer, style="NBR",
        )
        # Row 1 right: Sheet number / format
        add_text(
            self.msp, (xm + pad, y0 + pad),
            f"FL: {info.drawing_number}  {info.sheet_format}", th,
            layer=layer, style="NBR",
        )

        # Projection system symbol (truncated cone)
        self._draw_projection_symbol(x1 - 15 * s, y1 - 12 * s, 8 * s)

    def _draw_projection_symbol(
        self, cx: float, cy: float, size: float
    ) -> None:
        """Draw 1st/3rd diedro projection symbol."""
        layer = "PROJ-DIEDRO"
        s = size / 8.0

        if self.projection == ProjectionSystem.FIRST_DIEDRO:
            # Truncated cone: large circle left, small right with connecting lines
            # Large circle (front view)
            self.msp.add_circle(
                (cx - 2 * s, cy), 2 * s,
                dxfattribs={"layer": layer},
            )
            # Small circle (side view)
            self.msp.add_circle(
                (cx + 3 * s, cy), 1 * s,
                dxfattribs={"layer": layer},
            )
            # Centerlines
            self.msp.add_line(
                (cx - 4 * s, cy), (cx + 4 * s, cy),
                dxfattribs={"layer": layer, "linetype": "DASHDOT"},
            )
        else:
            # 3rd diedro: small circle left, large right
            self.msp.add_circle(
                (cx - 2 * s, cy), 1 * s,
                dxfattribs={"layer": layer},
            )
            self.msp.add_circle(
                (cx + 3 * s, cy), 2 * s,
                dxfattribs={"layer": layer},
            )
            self.msp.add_line(
                (cx - 3 * s, cy), (cx + 5 * s, cy),
                dxfattribs={"layer": layer, "linetype": "DASHDOT"},
            )

    # -------------------------------------------------------------------
    # Geometry drawing methods
    # -------------------------------------------------------------------

    def draw_line(
        self,
        p1: Point2D,
        p2: Point2D,
        layer: str = "PAR-ESTRU",
        line_type: LineType = LineType.A,
        color: Optional[int] = None,
    ) -> None:
        """Draw a line with NBR line type."""
        attrs = {"layer": layer}
        if line_type.pattern:
            attrs["linetype"] = line_type.ezdxf_name
        if color is not None:
            attrs["color"] = color
        self.msp.add_line(p1, p2, dxfattribs=attrs)

    def draw_polyline(
        self,
        points: List[Point2D],
        layer: str = "PAR-ESTRU",
        closed: bool = False,
        line_type: LineType = LineType.A,
        color: Optional[int] = None,
    ) -> None:
        """Draw a polyline (open or closed)."""
        attrs = {"layer": layer}
        if line_type.pattern:
            attrs["linetype"] = line_type.ezdxf_name
        if color is not None:
            attrs["color"] = color
        pl = self.msp.add_lwpolyline(points, dxfattribs=attrs)
        if closed:
            pl.close()

    def draw_rectangle(
        self,
        p1: Point2D,
        p2: Point2D,
        layer: str = "PAR-ESTRU",
        line_type: LineType = LineType.A,
        color: Optional[int] = None,
    ) -> None:
        """Draw a rectangle from two corner points."""
        x0, y0 = p1
        x1, y1 = p2
        self.draw_polyline(
            [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
            layer=layer, closed=True, line_type=line_type, color=color,
        )

    def draw_circle(
        self,
        center: Point2D,
        radius: float,
        layer: str = "PAR-ESTRU",
        color: Optional[int] = None,
    ) -> None:
        """Draw a circle."""
        attrs = {"layer": layer}
        if color is not None:
            attrs["color"] = color
        self.msp.add_circle(center, radius, dxfattribs=attrs)

    def draw_arc(
        self,
        center: Point2D,
        radius: float,
        start_angle: float,
        end_angle: float,
        layer: str = "PAR-ESTRU",
        color: Optional[int] = None,
    ) -> None:
        """Draw an arc (angles in degrees, counterclockwise from +X)."""
        attrs = {"layer": layer}
        if color is not None:
            attrs["color"] = color
        self.msp.add_arc(
            center, radius,
            start_angle=start_angle,
            end_angle=end_angle,
            dxfattribs=attrs,
        )

    def draw_wall(
        self,
        p1: Point2D,
        p2: Point2D,
        thickness: float = 0.15,
        layer: str = "PAR-ESTRU",
        is_structural: bool = True,
    ) -> None:
        """Draw a wall as two parallel lines with optional fill.

        Structural walls use wide lines (Type A), non-structural use narrow.
        """
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.sqrt(dx**2 + dy**2)
        if length < 1e-6:
            return

        # Normal direction
        nx = -dy / length * thickness / 2
        ny = dx / length * thickness / 2

        # Wall outline (4 corners)
        corners = [
            (p1[0] + nx, p1[1] + ny),
            (p2[0] + nx, p2[1] + ny),
            (p2[0] - nx, p2[1] - ny),
            (p1[0] - nx, p1[1] - ny),
        ]

        lt = LineType.A if is_structural else LineType.B
        wall_layer = layer if is_structural else "PAR-VEDA"
        self.draw_polyline(corners, layer=wall_layer, closed=True, line_type=lt)

        # Fill structural walls with solid hatch
        if is_structural:
            hatch = self.msp.add_hatch(
                color=8,
                dxfattribs={"layer": wall_layer},
            )
            hatch.set_solid_fill()
            hatch.paths.add_polyline_path(
                [(c[0], c[1]) for c in corners],
                is_closed=True,
            )

    def draw_door(
        self,
        position: Point2D,
        width: float,
        wall_thickness: float = 0.15,
        angle: float = 0.0,
        opening_side: str = "left",
        layer: str = "ESQ-PORTA",
    ) -> None:
        """Draw a door symbol (opening arc + leaf line).

        Per NBR 6492: door shown as arc indicating swing direction.
        """
        x, y = position
        cos_a = math.cos(math.radians(angle))
        sin_a = math.sin(math.radians(angle))

        # Door leaf line
        leaf_end = (
            x + width * cos_a,
            y + width * sin_a,
        )
        self.msp.add_line(
            position, leaf_end,
            dxfattribs={"layer": layer},
        )

        # Opening arc (90 degrees)
        if opening_side == "left":
            start_angle = angle
            end_angle = angle + 90
        else:
            start_angle = angle - 90
            end_angle = angle

        self.msp.add_arc(
            position, width,
            start_angle=start_angle,
            end_angle=end_angle,
            dxfattribs={"layer": layer},
        )

        # Wall opening (gap in wall)
        gap_start = (x - wall_thickness / 2 * sin_a, y + wall_thickness / 2 * cos_a)
        gap_end = (
            x + width * cos_a - wall_thickness / 2 * sin_a,
            y + width * sin_a + wall_thickness / 2 * cos_a,
        )

    def draw_window(
        self,
        p1: Point2D,
        p2: Point2D,
        wall_thickness: float = 0.15,
        layer: str = "ESQ-JANELA",
    ) -> None:
        """Draw a window symbol (double lines in wall opening).

        Per NBR 6492: window shown as parallel lines within wall.
        """
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.sqrt(dx**2 + dy**2)
        if length < 1e-6:
            return

        nx = -dy / length * wall_thickness / 2
        ny = dx / length * wall_thickness / 2

        # Glass lines at wall edges (NBR 6492: 2 parallel lines + end caps)
        self.msp.add_line(
            (p1[0] + nx * 0.8, p1[1] + ny * 0.8),
            (p2[0] + nx * 0.8, p2[1] + ny * 0.8),
            dxfattribs={"layer": layer},
        )
        self.msp.add_line(
            (p1[0] - nx * 0.8, p1[1] - ny * 0.8),
            (p2[0] - nx * 0.8, p2[1] - ny * 0.8),
            dxfattribs={"layer": layer},
        )
        # Peitoril lines (perpendicular end caps connecting the 2 glass lines)
        self.msp.add_line(
            (p1[0] + nx * 0.8, p1[1] + ny * 0.8),
            (p1[0] - nx * 0.8, p1[1] - ny * 0.8),
            dxfattribs={"layer": layer},
        )
        self.msp.add_line(
            (p2[0] + nx * 0.8, p2[1] + ny * 0.8),
            (p2[0] - nx * 0.8, p2[1] - ny * 0.8),
            dxfattribs={"layer": layer},
        )

    # -------------------------------------------------------------------
    # Dimensioning (delegates to primitives)
    # -------------------------------------------------------------------

    def add_dimension(
        self,
        p1: Point2D,
        p2: Point2D,
        offset: float = -0.5,
        text: Optional[str] = None,
        angle: float = 0.0,
    ) -> None:
        """Add a linear dimension."""
        add_linear_dimension(
            self.msp, p1, p2, offset,
            text=text, angle=angle,
            style_name=self._dim_style_name,
        )

    def add_chain_dim(
        self,
        points: List[Point2D],
        offset: float = -0.5,
        angle: float = 0.0,
        add_total: bool = True,
    ) -> None:
        """Add chain dimensions through points."""
        add_chain_dimensions(
            self.msp, points, offset,
            angle=angle,
            style_name=self._dim_style_name,
            add_total=add_total,
        )

    def add_radius_dim(
        self, center: Point2D, radius: float, angle: float = 45.0
    ) -> None:
        add_radius_dimension(
            self.msp, center, radius, angle,
            style_name=self._dim_style_name,
        )

    def add_diameter_dim(
        self, center: Point2D, radius: float, angle: float = 45.0
    ) -> None:
        add_diameter_dimension(
            self.msp, center, radius, angle,
            style_name=self._dim_style_name,
        )

    # -------------------------------------------------------------------
    # Annotations (delegates to primitives)
    # -------------------------------------------------------------------

    def add_text(
        self,
        position: Point2D,
        text: str,
        height: Optional[float] = None,
        layer: str = "TEXTO",
        **kwargs,
    ) -> None:
        """Add text at model-space coordinates.

        If height is None, uses scale-appropriate default.
        """
        if height is None:
            height = self.scale.text_height_mm(3.5) / 1000.0
        add_text(self.msp, position, text, height, layer=layer, style="Standard", **kwargs)

    def add_room_label(
        self,
        center: Point2D,
        name: str,
        area_m2: float,
    ) -> None:
        """Add room label with name and area."""
        th = self.scale.text_height_mm(3.5) / 1000.0
        add_room_label(self.msp, center, name, area_m2, text_height=th)

    def add_leader(
        self,
        target: Point2D,
        text_pos: Point2D,
        text: str,
    ) -> None:
        """Add leader/callout annotation."""
        th = self.scale.text_height_mm(2.5) / 1000.0
        add_leader(self.msp, target, text_pos, text, text_height=th)

    # -------------------------------------------------------------------
    # Hatching (delegates to primitives)
    # -------------------------------------------------------------------

    def add_hatch(
        self,
        boundary: List[Point2D],
        material: HatchMaterial = HatchMaterial.GENERIC,
    ) -> None:
        """Add material hatch to a boundary."""
        pattern = HatchPattern.for_material(material)
        add_hatch(self.msp, boundary, pattern)

    def add_section_hatch(
        self,
        boundary: List[Point2D],
        material: HatchMaterial = HatchMaterial.CONCRETE,
        index: int = 0,
    ) -> None:
        """Add section hatching with adjacent-part differentiation."""
        add_section_hatch(self.msp, boundary, material, section_index=index)

    # -------------------------------------------------------------------
    # Section indicators
    # -------------------------------------------------------------------

    def add_cutting_plane(
        self,
        start: Point2D,
        end: Point2D,
        label: str = "A",
    ) -> None:
        """Add cutting plane indicator with direction arrows."""
        add_cutting_plane(self.msp, start, end, label)

    # -------------------------------------------------------------------
    # Centerlines and axes
    # -------------------------------------------------------------------

    def draw_centerline(
        self,
        p1: Point2D,
        p2: Point2D,
        layer: str = "EIXO",
    ) -> None:
        """Draw a centerline (dash-dot, type G per NBR 8403)."""
        self.draw_line(p1, p2, layer=layer, line_type=LineType.G)

    def draw_hidden(
        self,
        p1: Point2D,
        p2: Point2D,
        layer: str = "OCULTA",
    ) -> None:
        """Draw a hidden edge (dashed, type E per NBR 8403)."""
        self.draw_line(p1, p2, layer=layer, line_type=LineType.E)

    # -------------------------------------------------------------------
    # Save
    # -------------------------------------------------------------------

    def save(self, filepath: str) -> str:
        """Save the drawing to a DXF file.

        Returns the absolute path of the saved file.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.saveas(str(path))
        logger.info(f"Drawing saved: {path}")
        return str(path.resolve())

    # -------------------------------------------------------------------
    # Model-aware drawing (BuildingModel integration)
    # -------------------------------------------------------------------

    def draw_plan(
        self, model, floor: int = 0, resolve_intersections: bool = True,
        auto_dim: bool = False,
    ) -> None:
        """Draw a complete floor plan from a BuildingModel.

        Draws walls (with material-correct thickness and hatch),
        openings (doors with arcs, windows with double lines),
        room labels, and columns/beams.

        Args:
            model: BuildingModel instance
            floor: Floor level to draw
            resolve_intersections: If True, merge walls at corners using
                Shapely (clean L/T junctions). If False, draw each wall
                independently (faster but overlapping corners).
            auto_dim: If True, auto-generate dimensions from model geometry.
        """
        from .building_model import BuildingModel
        assert isinstance(model, BuildingModel)

        floor_walls = model.walls_on_floor(floor)

        if resolve_intersections:
            # Use wall resolver for clean corners + opening voids
            from .wall_resolver import resolve_walls, draw_resolved_walls
            resolved = resolve_walls(floor_walls)
            draw_resolved_walls(self, resolved)
        else:
            # Legacy: draw each wall independently
            for wall in floor_walls:
                self.draw_wall(
                    wall.p1, wall.p2,
                    thickness=wall.thickness_m,
                    is_structural=wall.is_structural,
                )

        # Draw opening symbols (door arcs, window lines) — always on top
        for wall in floor_walls:
            for opening in wall.openings:
                pos = wall.point_at(opening.position_m)
                if opening.is_door:
                    self.draw_door(
                        pos, width=opening.width,
                        wall_thickness=wall.thickness_m,
                        angle=wall.angle_deg,
                        opening_side=opening.opening_side,
                    )
                elif opening.is_window:
                    end = wall.point_at(opening.position_m + opening.width)
                    self.draw_window(pos, end, wall_thickness=wall.thickness_m)

        # Draw columns
        for col in model.columns_on_floor(floor):
            cx, cy = col.position
            hw = col.member.width_m / 2
            hh = col.member.height_m / 2
            self.draw_rectangle(
                (cx - hw, cy - hh), (cx + hw, cy + hh),
                layer="PAR-ESTRU",
            )
            # Hatch column
            hatch = self.msp.add_hatch(
                color=253,
                dxfattribs={"layer": "PAR-ESTRU"},
            )
            hatch.set_solid_fill()
            hatch.paths.add_polyline_path(
                [(cx - hw, cy - hh), (cx + hw, cy - hh),
                 (cx + hw, cy + hh), (cx - hw, cy + hh)],
                is_closed=True,
            )

        # Draw room labels
        for room in model.rooms_on_floor(floor):
            self.add_room_label(room.center, room.name, room.area_m2)

        # Auto-dimensioning
        if auto_dim:
            from .auto_dim import auto_dimension_plan
            auto_dimension_plan(self, model, floor=floor)

    def draw_section_from_model(
        self,
        model,
        cut_start: Tuple[float, float],
        cut_end: Tuple[float, float],
        label: str = "A-A",
        direction: str = "north",
        origin: Tuple[float, float] = (0.0, 0.0),
        floor: int = 0,
    ) -> None:
        """Draw a building section from a BuildingModel."""
        from .views import SectionCut, generate_section_from_walls

        cut = SectionCut(
            label=label,
            start=cut_start,
            end=cut_end,
            direction=direction,
        )

        # Get slab thickness from model
        slabs = model.slabs_on_floor(floor)
        slab_t = slabs[0].thickness_m if slabs else 0.12

        # Roof profile for section
        roof_prof = model.roof_profile(direction="x") if model.roof else None

        # Foundation data
        fd = model.foundation.depth_m if model.foundation else 0
        fw = model.foundation.width_m if model.foundation else 0

        generate_section_from_walls(
            self,
            model.walls_as_tuples(floor),
            cut,
            origin=origin,
            ceiling_height=model.ceiling_height,
            slab_thickness=slab_t,
            roof_profile=roof_prof,
            foundation_depth=fd,
            foundation_width=fw,
        )

    def draw_elevation_from_model(
        self,
        model,
        direction: str = "south",
        origin: Tuple[float, float] = (0.0, 0.0),
        floor: int = 0,
        label: str = "",
    ) -> None:
        """Draw a building elevation from a BuildingModel."""
        from .perspectives import draw_elevation

        labels = {
            "south": "FACHADA FRONTAL (SUL)",
            "north": "FACHADA POSTERIOR (NORTE)",
            "east": "FACHADA LATERAL DIREITA (LESTE)",
            "west": "FACHADA LATERAL ESQUERDA (OESTE)",
        }

        # Roof profile for elevation
        axis = "x" if direction in ("east", "west") else "y"
        roof_prof = model.roof_profile(direction=axis) if model.roof else None

        draw_elevation(
            self,
            model.walls_as_tuples(floor),
            model.openings_as_dicts(floor),
            origin=origin,
            direction=direction,
            label=label or labels.get(direction, "FACHADA"),
            roof_profile=roof_prof,
        )

    def draw_isometric_from_model(
        self,
        model,
        origin: Tuple[float, float] = (0.15, 0.05),
        floor: int = 0,
        draw_hidden: bool = False,
    ) -> None:
        """Draw isometric perspective from a BuildingModel."""
        from .perspectives import draw_isometric_from_walls

        draw_isometric_from_walls(
            self,
            model.walls_as_tuples(floor),
            origin=origin,
            draw_hidden=draw_hidden,
        )

    @property
    def modelspace(self):
        """Direct access to ezdxf modelspace for advanced operations."""
        return self.msp
