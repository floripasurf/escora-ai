"""Orthographic view generator — multi-view projection per NBR 10067.

Generates coordinated orthographic views (VF, VS, VLD, VLE, etc.)
from a 3D model or from 2D floor plan data, following 1st diedro conventions.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .nbr import (
    ProjectionSystem, ViewArrangement, SectionType,
    LineType, HatchMaterial, Scale,
)
from .sheet import TechnicalSheet, Point2D
from .primitives import add_text, add_cutting_plane, add_section_hatch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 3D Geometry representation (simple box model)
# ---------------------------------------------------------------------------

@dataclass
class Face:
    """A planar face of a 3D solid."""
    vertices: List[Tuple[float, float, float]]  # 3D vertices
    normal: Tuple[float, float, float] = (0, 0, 1)
    is_visible: bool = True
    material: Optional[HatchMaterial] = None

    @property
    def is_horizontal(self) -> bool:
        return abs(self.normal[2]) > 0.9

    @property
    def is_vertical(self) -> bool:
        return abs(self.normal[2]) < 0.1


@dataclass
class Solid3D:
    """Simple 3D solid for projection (box, cylinder, prism)."""
    faces: List[Face] = field(default_factory=list)
    name: str = ""

    @classmethod
    def box(
        cls,
        origin: Tuple[float, float, float],
        width: float,
        depth: float,
        height: float,
        name: str = "",
    ) -> "Solid3D":
        """Create a rectangular box solid."""
        x, y, z = origin
        # 6 faces
        faces = [
            # Bottom (Z=z, normal -Z)
            Face([(x, y, z), (x + width, y, z),
                  (x + width, y + depth, z), (x, y + depth, z)],
                 normal=(0, 0, -1)),
            # Top (Z=z+h, normal +Z)
            Face([(x, y, z + height), (x + width, y, z + height),
                  (x + width, y + depth, z + height), (x, y + depth, z + height)],
                 normal=(0, 0, 1)),
            # Front (Y=y, normal -Y)
            Face([(x, y, z), (x + width, y, z),
                  (x + width, y, z + height), (x, y, z + height)],
                 normal=(0, -1, 0)),
            # Back (Y=y+d, normal +Y)
            Face([(x, y + depth, z), (x + width, y + depth, z),
                  (x + width, y + depth, z + height), (x, y + depth, z + height)],
                 normal=(0, 1, 0)),
            # Left (X=x, normal -X)
            Face([(x, y, z), (x, y + depth, z),
                  (x, y + depth, z + height), (x, y, z + height)],
                 normal=(-1, 0, 0)),
            # Right (X=x+w, normal +X)
            Face([(x + width, y, z), (x + width, y + depth, z),
                  (x + width, y + depth, z + height), (x + width, y, z + height)],
                 normal=(1, 0, 0)),
        ]
        return cls(faces=faces, name=name)

    @classmethod
    def from_floor_plan(
        cls,
        walls: List[Tuple[Point2D, Point2D, float]],  # (start, end, height)
        wall_thickness: float = 0.15,
        name: str = "",
    ) -> "Solid3D":
        """Create a 3D model from 2D wall segments.

        Each wall becomes a vertical box solid.
        """
        solid = cls(name=name)
        for (p1, p2, height) in walls:
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = math.sqrt(dx**2 + dy**2)
            if length < 1e-6:
                continue
            # Create wall box aligned to wall direction
            wall_box = cls.box(
                (p1[0], p1[1], 0),
                length, wall_thickness, height,
            )
            solid.faces.extend(wall_box.faces)
        return solid


# ---------------------------------------------------------------------------
# Orthographic Projection
# ---------------------------------------------------------------------------

def _project_face_to_view(
    face: Face,
    view: str,
) -> Optional[List[Point2D]]:
    """Project a 3D face onto a 2D view plane.

    Returns 2D polygon or None if face is edge-on (projects to a line).
    """
    projections = {
        # view: (x_axis_3d, y_axis_3d)
        "VF": (0, 2),   # Front: X→x, Z→y
        "VS": (0, 1),   # Top:   X→x, Y→y
        "VLD": (1, 2),  # Right: Y→x, Z→y
        "VLE": (1, 2),  # Left:  Y→x (inverted), Z→y
        "VP": (0, 2),   # Back:  X→x (inverted), Z→y
        "VI": (0, 1),   # Bottom: X→x, Y→y (inverted)
    }

    if view not in projections:
        return None

    ax, ay = projections[view]
    projected = []
    for v in face.vertices:
        x = v[ax]
        y = v[ay]
        # Invert axes for certain views
        if view == "VLE":
            x = -x
        elif view == "VP":
            x = -x
        elif view == "VI":
            y = -y
        projected.append((x, y))

    # Check if projection is degenerate (all points collinear)
    if len(projected) >= 3:
        # Simple area check
        area = 0.0
        n = len(projected)
        for i in range(n):
            j = (i + 1) % n
            area += projected[i][0] * projected[j][1]
            area -= projected[j][0] * projected[i][1]
        area = abs(area) / 2.0
        if area < 1e-8:
            return None  # Edge-on, projects to a line

    return projected


def _is_face_visible(face: Face, view: str) -> bool:
    """Check if face is visible (front-facing) for the given view direction."""
    view_dirs = {
        "VF": (0, -1, 0),   # Looking from front (−Y direction)
        "VS": (0, 0, -1),   # Looking from top (−Z direction)
        "VLD": (1, 0, 0),   # Looking from right (+X direction)
        "VLE": (-1, 0, 0),  # Looking from left (−X direction)
        "VP": (0, 1, 0),    # Looking from back (+Y direction)
        "VI": (0, 0, 1),    # Looking from bottom (+Z direction)
    }
    if view not in view_dirs:
        return False
    vd = view_dirs[view]
    dot = sum(a * b for a, b in zip(face.normal, vd))
    return dot < 0  # Face normal points toward viewer


# ---------------------------------------------------------------------------
# Multi-View Layout
# ---------------------------------------------------------------------------

@dataclass
class ViewPort:
    """A single view positioned on the sheet."""
    name: str          # "VF", "VS", "VLD", etc.
    label: str         # Human-readable label
    origin_x: float    # Origin X on sheet (model coords)
    origin_y: float    # Origin Y on sheet
    width: float       # View width
    height: float      # View height


def layout_views(
    model_width: float,
    model_depth: float,
    model_height: float,
    views: List[str] = None,
    gap: float = 2.0,
    system: ProjectionSystem = ProjectionSystem.FIRST_DIEDRO,
) -> List[ViewPort]:
    """Calculate view positions for multi-view orthographic layout.

    Args:
        model_width: Object width (X)
        model_depth: Object depth (Y)
        model_height: Object height (Z)
        views: Which views to include (default: VF, VS, VLD)
        gap: Spacing between views in model units
        system: Projection system

    Returns:
        List of ViewPort with calculated positions
    """
    if views is None:
        views = ["VF", "VS", "VLD"]

    arrangement = ViewArrangement(system)
    viewports = []

    # View dimensions per projection direction
    view_dims = {
        "VF": (model_width, model_height),
        "VS": (model_width, model_depth),
        "VI": (model_width, model_depth),
        "VLD": (model_depth, model_height),
        "VLE": (model_depth, model_height),
        "VP": (model_width, model_height),
    }

    # View labels
    view_labels = {
        "VF": "VISTA FRONTAL",
        "VS": "VISTA SUPERIOR",
        "VI": "VISTA INFERIOR",
        "VLD": "VISTA LAT. DIREITA",
        "VLE": "VISTA LAT. ESQUERDA",
        "VP": "VISTA POSTERIOR",
    }

    # Place VF at origin
    vf_w, vf_h = view_dims.get("VF", (model_width, model_height))
    vf_x, vf_y = 0.0, 0.0

    for view_name in views:
        w, h = view_dims.get(view_name, (model_width, model_height))
        col_off, row_off = arrangement.view_position(view_name)

        # Position based on grid offset from VF
        ox = vf_x + col_off * (vf_w + gap)
        oy = vf_y + row_off * (vf_h + gap)

        # Adjust for different view sizes (alignment)
        if row_off != 0:
            # Vertical neighbor: align left edges
            pass
        if col_off != 0:
            # Horizontal neighbor: align bottom edges
            pass

        viewports.append(ViewPort(
            name=view_name,
            label=view_labels.get(view_name, view_name),
            origin_x=ox,
            origin_y=oy,
            width=w,
            height=h,
        ))

    return viewports


def draw_orthographic_views(
    sheet: TechnicalSheet,
    solids: List[Solid3D],
    views: List[str] = None,
    origin: Point2D = (0.0, 0.0),
    gap: float = 2.0,
) -> List[ViewPort]:
    """Draw multi-view orthographic projections on a TechnicalSheet.

    Args:
        sheet: Target drawing sheet
        solids: 3D solids to project
        views: Which views (default: VF, VS, VLD)
        origin: Starting position on sheet
        gap: Spacing between views

    Returns:
        List of ViewPort with positions used
    """
    if views is None:
        views = ["VF", "VS", "VLD"]

    # Calculate bounding box of all solids
    all_verts = []
    for s in solids:
        for f in s.faces:
            all_verts.extend(f.vertices)

    if not all_verts:
        return []

    xs = [v[0] for v in all_verts]
    ys = [v[1] for v in all_verts]
    zs = [v[2] for v in all_verts]
    model_w = max(xs) - min(xs)
    model_d = max(ys) - min(ys)
    model_h = max(zs) - min(zs)

    # Layout views
    viewports = layout_views(
        model_w, model_d, model_h,
        views=views, gap=gap,
        system=sheet.projection,
    )

    # Draw each view
    for vp in viewports:
        ox = origin[0] + vp.origin_x
        oy = origin[1] + vp.origin_y

        for solid in solids:
            for face in solid.faces:
                visible = _is_face_visible(face, vp.name)
                projected = _project_face_to_view(face, vp.name)

                if projected is None:
                    continue

                # Offset to view position
                offset_pts = [(p[0] + ox, p[1] + oy) for p in projected]

                if visible:
                    # Visible contour — Type A (continuous wide)
                    sheet.draw_polyline(
                        offset_pts,
                        layer="PAR-ESTRU",
                        closed=True,
                        line_type=LineType.A,
                    )
                else:
                    # Hidden edge — Type E (dashed)
                    sheet.draw_polyline(
                        offset_pts,
                        layer="OCULTA",
                        closed=True,
                        line_type=LineType.E,
                    )

        # View label
        label_y = oy - 0.3
        sheet.add_text(
            (ox + vp.width / 2, label_y),
            vp.label,
            halign="CENTER",
        )

        # View border (thin dashed for alignment reference)
        sheet.draw_rectangle(
            (ox - 0.1, oy - 0.1),
            (ox + vp.width + 0.1, oy + vp.height + 0.1),
            layer="EIXO",
            line_type=LineType.K,
            color=9,
        )

    return viewports


# ---------------------------------------------------------------------------
# Section (Corte) Generation
# ---------------------------------------------------------------------------

@dataclass
class SectionCut:
    """Definition of a section cut through a building."""
    label: str              # "A-A", "B-B"
    start: Point2D          # Start of cutting plane on plan
    end: Point2D            # End of cutting plane on plan
    direction: str          # "north", "south", "east", "west" — viewing direction
    section_type: SectionType = SectionType.FULL
    height_m: float = 2.80  # Cut height for horizontal sections


def generate_section_from_walls(
    sheet: TechnicalSheet,
    walls: List[Tuple[Point2D, Point2D, float, float]],  # start, end, height, thickness
    cut: SectionCut,
    origin: Point2D = (0.0, 0.0),
    floor_height: float = 0.0,
    ceiling_height: float = 2.80,
    slab_thickness: float = 0.12,
    roof_profile: Optional[List[Point2D]] = None,
    foundation_depth: float = 0.0,
    foundation_width: float = 0.0,
) -> None:
    """Generate a building section (corte) from wall data.

    Draws the section view at the specified origin on the sheet,
    showing walls cut by the section plane with hatching,
    and elements visible behind the cut plane.

    Args:
        sheet: Target drawing sheet
        walls: List of (start, end, height, thickness) wall segments
        cut: Section cut definition
        origin: Where to draw the section on sheet
        floor_height: Height of floor level
        ceiling_height: Ceiling height above floor
        slab_thickness: Thickness of floor/ceiling slab
        roof_profile: List of (x, y) points for roof outline (from BuildingModel)
        foundation_depth: Foundation depth below floor slab (m)
        foundation_width: Foundation width (m)
    """
    ox, oy = origin

    # Determine cutting line direction
    cut_dx = cut.end[0] - cut.start[0]
    cut_dy = cut.end[1] - cut.start[1]
    cut_len = math.sqrt(cut_dx**2 + cut_dy**2)
    if cut_len < 1e-6:
        return

    cut_ux = cut_dx / cut_len
    cut_uy = cut_dy / cut_len

    section_idx = 0

    for wall_start, wall_end, wall_h, wall_t in walls:
        # Check if wall intersects cutting plane
        # Simplified: check if wall crosses the cut line
        # Project wall endpoints onto cut normal
        nx, ny = -cut_uy, cut_ux  # Normal to cut line

        d1 = (wall_start[0] - cut.start[0]) * nx + (wall_start[1] - cut.start[1]) * ny
        d2 = (wall_end[0] - cut.start[0]) * nx + (wall_end[1] - cut.start[1]) * ny

        if d1 * d2 <= 0:
            # Wall crosses cutting plane — draw as cut (with hatch)
            # Project intersection point onto cut line
            t = d1 / (d1 - d2) if abs(d1 - d2) > 1e-6 else 0.5
            ix = wall_start[0] + t * (wall_end[0] - wall_start[0])
            iy = wall_start[1] + t * (wall_end[1] - wall_start[1])

            # Position along cut line
            along = (ix - cut.start[0]) * cut_ux + (iy - cut.start[1]) * cut_uy

            # Draw wall section rectangle (thickness x height)
            x0 = ox + along - wall_t / 2
            x1 = ox + along + wall_t / 2
            y0 = oy + floor_height
            y1 = oy + floor_height + wall_h

            # Wall outline
            wall_rect = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            sheet.draw_polyline(wall_rect, layer="PAR-ESTRU", closed=True)

            # Section hatch
            add_section_hatch(
                sheet.msp, wall_rect,
                material=HatchMaterial.BRICK,
                section_index=section_idx,
            )
            section_idx += 1

        elif (d1 > 0 and cut.direction in ("north", "east")) or \
             (d1 < 0 and cut.direction in ("south", "west")):
            # Wall behind cutting plane — draw as visible (no hatch)
            wall_dx = wall_end[0] - wall_start[0]
            wall_dy = wall_end[1] - wall_start[1]
            wall_len = math.sqrt(wall_dx**2 + wall_dy**2)

            # Project wall onto cut line
            along1 = (wall_start[0] - cut.start[0]) * cut_ux + \
                      (wall_start[1] - cut.start[1]) * cut_uy
            along2 = (wall_end[0] - cut.start[0]) * cut_ux + \
                      (wall_end[1] - cut.start[1]) * cut_uy

            x0 = ox + min(along1, along2)
            x1 = ox + max(along1, along2)
            y0 = oy + floor_height
            y1 = oy + floor_height + wall_h

            # Draw as visible contour (no hatch)
            sheet.draw_polyline(
                [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                layer="PAR-ESTRU", closed=True,
            )

    # Draw floor slab
    total_width = cut_len
    slab_rect = [
        (ox, oy + floor_height - slab_thickness),
        (ox + total_width, oy + floor_height - slab_thickness),
        (ox + total_width, oy + floor_height),
        (ox, oy + floor_height),
    ]
    sheet.draw_polyline(slab_rect, layer="PAR-ESTRU", closed=True)
    add_section_hatch(
        sheet.msp, slab_rect,
        material=HatchMaterial.CONCRETE,
        section_index=99,
    )

    # Draw ceiling slab
    ceil_rect = [
        (ox, oy + ceiling_height),
        (ox + total_width, oy + ceiling_height),
        (ox + total_width, oy + ceiling_height + slab_thickness),
        (ox, oy + ceiling_height + slab_thickness),
    ]
    sheet.draw_polyline(ceil_rect, layer="PAR-ESTRU", closed=True)
    add_section_hatch(
        sheet.msp, ceil_rect,
        material=HatchMaterial.CONCRETE,
        section_index=100,
    )

    # Draw roof profile if provided
    if roof_profile:
        roof_pts = [(ox + p[0], oy + p[1]) for p in roof_profile]
        sheet.draw_polyline(roof_pts, layer="PAR-ESTRU", line_type=LineType.A)

    # Draw foundation if provided
    if foundation_depth > 0:
        fd = foundation_depth
        fw = foundation_width
        # Draw foundation blocks under each cut wall
        for wall_start, wall_end, wall_h, wall_t in walls:
            nx, ny = -cut_uy, cut_ux
            d1 = (wall_start[0] - cut.start[0]) * nx + (wall_start[1] - cut.start[1]) * ny
            d2 = (wall_end[0] - cut.start[0]) * nx + (wall_end[1] - cut.start[1]) * ny
            if d1 * d2 <= 0:
                t = d1 / (d1 - d2) if abs(d1 - d2) > 1e-6 else 0.5
                ix = wall_start[0] + t * (wall_end[0] - wall_start[0])
                iy = wall_start[1] + t * (wall_end[1] - wall_start[1])
                along = (ix - cut.start[0]) * cut_ux + (iy - cut.start[1]) * cut_uy
                fx0 = ox + along - fw / 2
                fx1 = ox + along + fw / 2
                fy0 = oy + floor_height - slab_thickness - fd
                fy1 = oy + floor_height - slab_thickness
                found_rect = [(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)]
                sheet.draw_polyline(found_rect, layer="PAR-ESTRU", closed=True)
                add_section_hatch(
                    sheet.msp, found_rect,
                    material=HatchMaterial.CONCRETE,
                    section_index=200,
                )

    # Section label
    label_text = f"CORTE {cut.label}"
    sheet.add_text(
        (ox + total_width / 2, oy - 0.5),
        label_text,
        halign="CENTER",
    )

    # Scale reference
    sheet.add_text(
        (ox + total_width / 2, oy - 0.8),
        sheet.scale.label,
        halign="CENTER",
        color=8,
    )
