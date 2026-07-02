"""Perspective generators — isometric, cavaleira, and elevation views.

Generates 2D perspective projections from 3D data following NBR conventions:
- Isometric: 3 axes at 120 degrees, 1:1:1 scale (simplified method)
- Cavaleira: front face true shape, depth at 30/45/60 degrees with reduction
- Elevation (fachada): orthographic front/side views with materials and finishes
"""

import math
import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .nbr import LineType
from .sheet import TechnicalSheet, Point2D

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Isometric Projection (Perspectiva Isométrica)
# ---------------------------------------------------------------------------

# Isometric axes: 30 degrees from horizontal
ISO_ANGLE = math.radians(30)
ISO_COS = math.cos(ISO_ANGLE)  # ~0.866
ISO_SIN = math.sin(ISO_ANGLE)  # 0.5


def iso_project(x: float, y: float, z: float) -> Point2D:
    """Project a 3D point to isometric 2D coordinates.

    Simplified isometric: same scale on all 3 axes.
    X-axis: 30 degrees right-down
    Y-axis: 30 degrees left-down
    Z-axis: vertical up
    """
    px = (x - y) * ISO_COS
    py = (x + y) * ISO_SIN + z
    return (px, py)


def draw_isometric_box(
    sheet: TechnicalSheet,
    origin: Point2D,
    x: float, y: float, z: float,
    width: float, depth: float, height: float,
    layer: str = "PAR-ESTRU",
    draw_hidden: bool = False,
    color: Optional[int] = None,
) -> None:
    """Draw a box in isometric projection.

    Args:
        sheet: Target drawing sheet
        origin: 2D origin on sheet for the isometric view
        x, y, z: 3D position of box corner
        width: Box width (X-axis)
        depth: Box depth (Y-axis)
        height: Box height (Z-axis)
        layer: Target layer
        draw_hidden: If True, draw hidden edges as dashed
        color: Optional color override
    """
    ox, oy = origin

    # 8 corners of the box
    corners_3d = [
        (x, y, z),                          # 0: front-bottom-left
        (x + width, y, z),                  # 1: front-bottom-right
        (x + width, y + depth, z),          # 2: back-bottom-right
        (x, y + depth, z),                  # 3: back-bottom-left
        (x, y, z + height),                 # 4: front-top-left
        (x + width, y, z + height),         # 5: front-top-right
        (x + width, y + depth, z + height), # 6: back-top-right
        (x, y + depth, z + height),         # 7: back-top-left
    ]

    # Project all corners
    pts = [(ox + iso_project(*c)[0], oy + iso_project(*c)[1]) for c in corners_3d]

    # Visible edges (always drawn)
    visible_edges = [
        (0, 1), (1, 5), (5, 4), (4, 0),  # Front face
        (1, 2), (2, 6), (6, 5),           # Right face
        (4, 7), (7, 6),                    # Top face
    ]

    for i, j in visible_edges:
        sheet.draw_line(pts[i], pts[j], layer=layer, line_type=LineType.A, color=color)

    # Hidden edges (optionally drawn as dashed)
    if draw_hidden:
        hidden_edges = [
            (0, 3), (3, 2),  # Bottom-back
            (3, 7),          # Left-back vertical
        ]
        for i, j in hidden_edges:
            sheet.draw_hidden(pts[i], pts[j])


def draw_isometric_from_walls(
    sheet: TechnicalSheet,
    walls: List[Tuple[Point2D, Point2D, float, float]],  # start, end, height, thickness
    origin: Point2D = (0.0, 0.0),
    draw_hidden: bool = False,
    floor_level: float = 0.0,
) -> None:
    """Draw a building in isometric from wall segments.

    Each wall is drawn as a 3D box projected to isometric.
    """
    for wall_start, wall_end, height, thickness in walls:
        dx = wall_end[0] - wall_start[0]
        dy = wall_end[1] - wall_start[1]
        length = math.sqrt(dx**2 + dy**2)
        if length < 1e-6:
            continue

        # Normal direction for thickness
        nx = -dy / length * thickness
        ny = dx / length * thickness

        # Wall as 3D box: we need to handle arbitrary orientation
        # For simplicity, approximate as axis-aligned boxes for cardinal walls
        if abs(dx) > abs(dy):
            # Mostly horizontal wall
            x0 = min(wall_start[0], wall_end[0])
            draw_isometric_box(
                sheet, origin,
                x0, wall_start[1] - thickness / 2, floor_level,
                abs(dx), thickness, height,
                draw_hidden=draw_hidden,
            )
        else:
            # Mostly vertical wall
            y0 = min(wall_start[1], wall_end[1])
            draw_isometric_box(
                sheet, origin,
                wall_start[0] - thickness / 2, y0, floor_level,
                thickness, abs(dy), height,
                draw_hidden=draw_hidden,
            )


def draw_isometric_circle(
    sheet: TechnicalSheet,
    origin: Point2D,
    center_3d: Tuple[float, float, float],
    radius: float,
    plane: str = "xy",
    segments: int = 36,
    layer: str = "PAR-ESTRU",
) -> None:
    """Draw a circle in isometric (appears as ellipse).

    Uses the 4-arc approximation method for circles on isometric planes.
    For simplicity, uses polyline approximation with sufficient segments.
    """
    ox, oy = origin
    cx, cy, cz = center_3d
    points = []

    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        if plane == "xy":
            px = cx + radius * math.cos(angle)
            py = cy + radius * math.sin(angle)
            pz = cz
        elif plane == "xz":
            px = cx + radius * math.cos(angle)
            py = cy
            pz = cz + radius * math.sin(angle)
        elif plane == "yz":
            px = cx
            py = cy + radius * math.cos(angle)
            pz = cz + radius * math.sin(angle)
        else:
            continue

        iso_pt = iso_project(px, py, pz)
        points.append((ox + iso_pt[0], oy + iso_pt[1]))

    sheet.draw_polyline(points, layer=layer, closed=True)


# ---------------------------------------------------------------------------
# Cavaleira Projection (Perspectiva Cavaleira)
# ---------------------------------------------------------------------------

@dataclass
class CavaleiraConfig:
    """Configuration for cavaleira (oblique) projection."""
    depth_angle_deg: float = 45.0       # 30, 45, or 60 degrees
    depth_reduction: float = 0.5        # 2/3 (30°), 1/2 (45°), 1/3 (60°)

    @classmethod
    def angle_30(cls) -> "CavaleiraConfig":
        return cls(depth_angle_deg=30.0, depth_reduction=2.0 / 3.0)

    @classmethod
    def angle_45(cls) -> "CavaleiraConfig":
        return cls(depth_angle_deg=45.0, depth_reduction=0.5)

    @classmethod
    def angle_60(cls) -> "CavaleiraConfig":
        return cls(depth_angle_deg=60.0, depth_reduction=1.0 / 3.0)


def cav_project(
    x: float, y: float, z: float,
    config: CavaleiraConfig,
) -> Point2D:
    """Project a 3D point to cavaleira 2D coordinates.

    Front face (X-Z plane) is drawn at true scale.
    Depth (Y-axis) is drawn at reduced scale at the configured angle.
    """
    angle_rad = math.radians(config.depth_angle_deg)
    px = x + y * config.depth_reduction * math.cos(angle_rad)
    py = z + y * config.depth_reduction * math.sin(angle_rad)
    return (px, py)


def draw_cavaleira_box(
    sheet: TechnicalSheet,
    origin: Point2D,
    x: float, y: float, z: float,
    width: float, depth: float, height: float,
    config: Optional[CavaleiraConfig] = None,
    layer: str = "PAR-ESTRU",
    draw_hidden: bool = False,
) -> None:
    """Draw a box in cavaleira projection."""
    if config is None:
        config = CavaleiraConfig.angle_45()

    ox, oy = origin

    corners_3d = [
        (x, y, z),
        (x + width, y, z),
        (x + width, y + depth, z),
        (x, y + depth, z),
        (x, y, z + height),
        (x + width, y, z + height),
        (x + width, y + depth, z + height),
        (x, y + depth, z + height),
    ]

    pts = [(ox + cav_project(*c, config)[0], oy + cav_project(*c, config)[1])
           for c in corners_3d]

    # Visible edges
    visible_edges = [
        (0, 1), (1, 5), (5, 4), (4, 0),  # Front face (true shape)
        (1, 2), (2, 6), (6, 5),           # Right face
        (4, 7), (7, 6),                    # Top face
    ]
    for i, j in visible_edges:
        sheet.draw_line(pts[i], pts[j], layer=layer, line_type=LineType.A)

    if draw_hidden:
        hidden_edges = [(0, 3), (3, 2), (3, 7)]
        for i, j in hidden_edges:
            sheet.draw_hidden(pts[i], pts[j])


# ---------------------------------------------------------------------------
# Elevation / Facade (Fachada)
# ---------------------------------------------------------------------------

def draw_elevation(
    sheet: TechnicalSheet,
    walls: List,
    openings: List[dict],
    origin: Point2D = (0.0, 0.0),
    direction: str = "south",
    ground_level: float = 0.0,
    terrain_slope: float = 0.0,
    label: str = "FACHADA FRONTAL",
    roof_profile: Optional[List[Point2D]] = None,
) -> None:
    """Draw a building elevation (fachada) view.

    Draws a single exterior contour (no individual wall rectangles) with
    integrated roof profile. Filters openings by wall orientation and
    position so only the correct facade's openings appear.

    Args:
        sheet: Target drawing sheet
        walls: Wall tuples — 4-element (p1, p2, h, t) or
               6-element (p1, p2, h, t, is_structural, angle_deg)
        openings: Dicts with type, x, y, width, height, sill_height,
                  wall_angle, wall_mid_x, wall_mid_y
        origin: Drawing origin on sheet
        direction: Viewing direction ("south", "north", "east", "west")
        ground_level: Ground level height
        terrain_slope: Terrain slope angle (degrees)
        label: View label
        roof_profile: Roof outline points (horizontal_pos, height)
    """
    if not walls:
        return

    ox, oy = origin

    # Compute horizontal extents and perpendicular extents for filtering
    if direction in ("south", "north"):
        h_coords = [c for w in walls for c in (w[0][0], w[1][0])]
        p_coords = [c for w in walls for c in (w[0][1], w[1][1])]
    else:
        h_coords = [c for w in walls for c in (w[0][1], w[1][1])]
        p_coords = [c for w in walls for c in (w[0][0], w[1][0])]

    h_min = min(h_coords)
    h_max = max(h_coords)
    p_min = min(p_coords)
    p_max = max(p_coords)

    height = max(w[2] for w in walls)

    # --- Exterior contour as single polyline (Bug 2+3 fix) ---
    contour = [
        (ox + h_min, oy + ground_level),            # bottom-left
        (ox + h_min, oy + ground_level + height),    # top-left
    ]

    if roof_profile:
        for p in roof_profile:
            contour.append((ox + p[0], oy + p[1]))
        contour.append((ox + h_max, oy + ground_level + height))  # top-right
    else:
        contour.append((ox + h_max, oy + ground_level + height))  # top-right

    contour.append((ox + h_max, oy + ground_level))  # bottom-right

    sheet.draw_polyline(contour, layer="PAR-ESTRU", closed=True, line_type=LineType.A)

    # --- Filter and draw openings (Bug 1 fix) ---
    ANGLE_TOL = 15  # degrees tolerance

    # Perpendicular target: which facade face are we showing?
    perp_target = {
        "south": p_min, "north": p_max,
        "east": p_max, "west": p_min,
    }[direction]

    for opening in openings:
        wall_angle = opening.get("wall_angle", 0)

        if direction in ("south", "north"):
            # Only openings in horizontal walls (angle ≈ 0° or ≈ 180°)
            angle_mod = abs(wall_angle) % 180
            if angle_mod > ANGLE_TOL and angle_mod < (180 - ANGLE_TOL):
                continue
            # Only openings on the correct face
            wall_mid_perp = opening.get("wall_mid_y", 0)
            if abs(wall_mid_perp - perp_target) > 0.5:
                continue
            op_x = opening.get("x", 0)
        else:
            # Only openings in vertical walls (angle ≈ 90° or ≈ -90°)
            if abs(abs(wall_angle) - 90) > ANGLE_TOL:
                continue
            wall_mid_perp = opening.get("wall_mid_x", 0)
            if abs(wall_mid_perp - perp_target) > 0.5:
                continue
            op_x = opening.get("y", 0)

        op_w = opening.get("width", 1.0)
        op_h = opening.get("height", 1.2)
        sill = opening.get("sill_height", 1.0)
        op_type = opening.get("type", "window")

        x0 = ox + op_x
        x1 = ox + op_x + op_w
        y0 = oy + ground_level + sill
        y1 = oy + ground_level + sill + op_h

        if op_type == "window":
            sheet.draw_rectangle((x0, y0), (x1, y1), layer="ESQ-JANELA")
            mid_y = (y0 + y1) / 2
            sheet.draw_line((x0, mid_y), (x1, mid_y), layer="ESQ-JANELA", line_type=LineType.B)
            mid_x = (x0 + x1) / 2
            sheet.draw_line((mid_x, y0), (mid_x, y1), layer="ESQ-JANELA", line_type=LineType.B)

        elif op_type == "door":
            y0 = oy + ground_level
            sheet.draw_rectangle((x0, y0), (x1, y1), layer="ESQ-PORTA")
            mid_x = (x0 + x1) / 2
            sheet.draw_line((mid_x, y0), (mid_x, y1), layer="ESQ-PORTA", line_type=LineType.B)
            handle_x = mid_x - op_w * 0.05
            handle_y = y0 + op_h * 0.45
            sheet.draw_circle((handle_x, handle_y), 0.02, layer="ESQ-PORTA")

    # Terrain line
    sheet.draw_line(
        (ox + h_min - 1.0, oy + ground_level),
        (ox + h_max + 1.0, oy + ground_level),
        layer="PAR-ESTRU",
        line_type=LineType.A,
    )

    # Label
    sheet.add_text(
        (ox + (h_min + h_max) / 2, oy + ground_level - 0.5),
        label,
        halign="CENTER",
    )
