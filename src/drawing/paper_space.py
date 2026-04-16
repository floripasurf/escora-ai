"""Paper space / viewport management — multi-scale layouts on a single sheet.

Implements ezdxf paper space (Layout) with viewports, allowing different
views at different scales on the same DXF sheet. Title block is always
drawn in paper space at 1:1.

Per NBR 8196: multiple scales can coexist on the same sheet when each
viewport has its scale clearly indicated.

Usage:
    from src.drawing.paper_space import PaperSpaceLayout

    ps = PaperSpaceLayout(sheet, "A1")
    ps.add_viewport("plan", x=20, y=60, width=400, height=350, scale=50)
    ps.add_viewport("detail", x=450, y=60, width=150, height=150, scale=20)
    ps.finalize()
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ezdxf

from .nbr import SheetFormat

logger = logging.getLogger(__name__)


@dataclass
class ViewportDef:
    """Definition of a viewport in paper space."""
    name: str
    x_mm: float             # Position in paper space (mm from left)
    y_mm: float             # Position in paper space (mm from bottom)
    width_mm: float         # Viewport width (mm)
    height_mm: float        # Viewport height (mm)
    scale_factor: float     # 1:50 → 50, 1:20 → 20
    center_model: Tuple[float, float] = (0.0, 0.0)  # Model space center point
    layer_visibility: Optional[Dict[str, bool]] = None  # Per-layer visibility


class PaperSpaceLayout:
    """Manages paper space layout with multiple viewports.

    Creates an ezdxf Layout (paper space) where:
    - Title block and border are drawn at 1:1 in paper space
    - Each viewport shows model space content at its own scale
    - Layer visibility can be controlled per viewport
    """

    def __init__(self, sheet, format_name: str = "A1"):
        self.sheet = sheet
        self.doc = sheet.doc
        self.fmt = SheetFormat[format_name]
        self.viewports: List[ViewportDef] = []

        # Create paper space layout
        self._layout = self.doc.layouts.new("Sheet1")
        self._layout_created = True

        logger.info(f"Paper space layout created: {format_name}")

    def add_viewport(
        self,
        name: str,
        x_mm: float,
        y_mm: float,
        width_mm: float,
        height_mm: float,
        scale_factor: float = 50,
        center_model: Optional[Tuple[float, float]] = None,
    ) -> None:
        """Add a viewport to the paper space layout.

        Args:
            name: Viewport identifier
            x_mm: Left edge position in paper space (mm)
            y_mm: Bottom edge position in paper space (mm)
            width_mm: Viewport width (mm)
            height_mm: Viewport height (mm)
            scale_factor: Scale denominator (e.g., 50 for 1:50)
            center_model: Center point in model space to show in viewport.
                If None, auto-centers based on bounding box.
        """
        if center_model is None:
            center_model = (0.0, 0.0)

        vp_def = ViewportDef(
            name=name,
            x_mm=x_mm,
            y_mm=y_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            scale_factor=scale_factor,
            center_model=center_model,
        )
        self.viewports.append(vp_def)

    def draw_paper_border(self) -> None:
        """Draw sheet border and margins in paper space (mm units)."""
        w = self.fmt.width_mm
        h = self.fmt.height_mm
        ml = self.fmt.margin_left_mm
        mo = self.fmt.margin_other_mm

        # Outer border
        self._layout.add_lwpolyline(
            [(0, 0), (w, 0), (w, h), (0, h), (0, 0)],
            dxfattribs={"lineweight": 50},
        )

        # Inner margin
        self._layout.add_lwpolyline(
            [(ml, mo), (w - mo, mo), (w - mo, h - mo), (ml, h - mo), (ml, mo)],
            dxfattribs={"lineweight": 25},
        )

    def draw_paper_title_block(self, info) -> None:
        """Draw title block in paper space (mm coordinates, 1:1 scale)."""
        w = self.fmt.width_mm
        h = self.fmt.height_mm
        mo = self.fmt.margin_other_mm
        lw = self.fmt.legend_width_mm
        lh = 50.0  # Legend height mm

        x0 = w - mo - lw
        y0 = mo
        x1 = w - mo
        y1 = mo + lh

        # Outer rectangle
        self._layout.add_lwpolyline(
            [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
            dxfattribs={"lineweight": 35},
        )

        # Horizontal divisions
        row_h = lh / 5
        for i in range(1, 5):
            y = y0 + row_h * i
            self._layout.add_line((x0, y), (x1, y))

        # Vertical division
        xm = x0 + lw * 0.6
        self._layout.add_line((xm, y0), (xm, y0 + row_h * 3))

        # Text entries
        th = 2.5
        th_title = 5.0
        pad = 2

        fields = [
            (x0 + pad, y0 + row_h * 4 + pad, info.project.upper(), th_title),
            (x0 + pad, y0 + row_h * 3 + pad, info.drawing_title, th),
            (x0 + pad, y0 + row_h * 2 + pad, f"RESP: {info.responsible or info.author}", th),
            (x0 + pad, y0 + row_h + pad, f"DATA: {info.date}", th),
            (xm + pad, y0 + row_h + pad, f"REV: {info.revision}", th),
            (x0 + pad, y0 + pad, f"ESCALA {info.scale_str}", th),
            (xm + pad, y0 + pad, f"FL: {info.drawing_number}  {info.sheet_format}", th),
        ]

        for x, y, text, height in fields:
            self._layout.add_text(
                text, height=height,
                dxfattribs={"style": "Standard"},
            ).set_placement((x, y))

    def finalize(self) -> None:
        """Create all viewports in paper space.

        Each viewport shows model space content at its own scale.
        Must be called after all viewports are added.
        """
        for vp_def in self.viewports:
            # Center of viewport in paper space
            cx = vp_def.x_mm + vp_def.width_mm / 2
            cy = vp_def.y_mm + vp_def.height_mm / 2

            # Model space size visible through viewport
            # viewport_width_mm / 1000 * scale_factor = model_width_m
            vp = self._layout.add_viewport(
                center=(cx, cy),
                size=(vp_def.width_mm, vp_def.height_mm),
                view_center_point=vp_def.center_model,
                view_height=vp_def.height_mm / 1000.0 * vp_def.scale_factor,
            )
            vp.dxf.status = 1  # Enable viewport

            # Add viewport label
            label_text = f"{vp_def.name} (1:{int(vp_def.scale_factor)})"
            self._layout.add_text(
                label_text, height=3.0,
                dxfattribs={"style": "Standard", "color": 8},
            ).set_placement(
                (vp_def.x_mm, vp_def.y_mm - 5),
            )

            # Draw viewport border (thin line)
            self._layout.add_lwpolyline(
                [
                    (vp_def.x_mm, vp_def.y_mm),
                    (vp_def.x_mm + vp_def.width_mm, vp_def.y_mm),
                    (vp_def.x_mm + vp_def.width_mm, vp_def.y_mm + vp_def.height_mm),
                    (vp_def.x_mm, vp_def.y_mm + vp_def.height_mm),
                    (vp_def.x_mm, vp_def.y_mm),
                ],
                dxfattribs={"lineweight": 13, "color": 8},
            )

        logger.info(f"Finalized {len(self.viewports)} viewports in paper space")

    @property
    def layout(self):
        """Direct access to ezdxf Layout for advanced operations."""
        return self._layout
