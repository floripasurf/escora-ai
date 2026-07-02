"""Auto-dimensioning — generates dimensions from BuildingModel per NBR 10126.

Automatically detects:
- External chain dimensions (total + wall segments along each axis)
- Internal room widths/depths
- Opening positions and widths
- Level marks on sections

NBR 10126 ordering: smaller dimensions closer to the object,
total dimension furthest away. No duplicate dimensions.

Usage:
    from src.drawing.auto_dim import auto_dimension_plan

    auto_dimension_plan(sheet, model)
"""

import logging
from typing import List, Set, Tuple

logger = logging.getLogger(__name__)

Point2D = Tuple[float, float]

# Tolerance for coordinate snapping (meters)
SNAP_TOL = 0.02


def _snap(val: float, tol: float = SNAP_TOL) -> float:
    """Round to tolerance grid to avoid near-duplicate coordinates."""
    return round(val / tol) * tol


def _unique_sorted(values: List[float]) -> List[float]:
    """Deduplicate and sort coordinate values."""
    snapped = sorted(set(_snap(v) for v in values))
    return snapped


def _collect_x_breakpoints(model, floor: int = 0) -> List[float]:
    """Collect all significant X coordinates from walls and openings."""
    xs: Set[float] = set()
    for w in model.walls_on_floor(floor):
        xs.add(_snap(w.p1[0]))
        xs.add(_snap(w.p2[0]))
        # Opening positions along horizontal walls
        if abs(w.p1[1] - w.p2[1]) < SNAP_TOL:  # Horizontal wall
            for o in w.openings:
                pos = w.point_at(o.position_m)
                end = w.point_at(o.position_m + o.width)
                xs.add(_snap(pos[0]))
                xs.add(_snap(end[0]))
    return sorted(xs)


def _collect_y_breakpoints(model, floor: int = 0) -> List[float]:
    """Collect all significant Y coordinates from walls and openings."""
    ys: Set[float] = set()
    for w in model.walls_on_floor(floor):
        ys.add(_snap(w.p1[1]))
        ys.add(_snap(w.p2[1]))
        # Opening positions along vertical walls
        if abs(w.p1[0] - w.p2[0]) < SNAP_TOL:  # Vertical wall
            for o in w.openings:
                pos = w.point_at(o.position_m)
                end = w.point_at(o.position_m + o.width)
                ys.add(_snap(pos[1]))
                ys.add(_snap(end[1]))
    return sorted(ys)


def _wall_x_coords(model, floor: int = 0) -> List[float]:
    """Unique X values of wall endpoints only (no openings)."""
    xs: Set[float] = set()
    for w in model.walls_on_floor(floor):
        xs.add(_snap(w.p1[0]))
        xs.add(_snap(w.p2[0]))
    return sorted(xs)


def _wall_y_coords(model, floor: int = 0) -> List[float]:
    """Unique Y values of wall endpoints only (no openings)."""
    ys: Set[float] = set()
    for w in model.walls_on_floor(floor):
        ys.add(_snap(w.p1[1]))
        ys.add(_snap(w.p2[1]))
    return sorted(ys)


def auto_dimension_plan(
    sheet,
    model,
    floor: int = 0,
    offset_first: float = -0.6,
    offset_step: float = -0.5,
    include_openings: bool = True,
    include_internal: bool = True,
) -> None:
    """Add automatic dimensions to a floor plan.

    Generates 3 layers of dimensions per NBR 10126:
    1. Opening dimensions (closest to wall) — if include_openings
    2. Wall segment dimensions (middle)
    3. Total dimension (furthest from wall)

    Does this for both horizontal (bottom) and vertical (left) axes.

    Args:
        sheet: TechnicalSheet instance
        model: BuildingModel instance
        floor: Floor level
        offset_first: Distance of first dimension row from object (m)
        offset_step: Spacing between dimension rows (m)
        include_openings: Add opening position dimensions
        include_internal: Add internal room dimensions
    """
    bb = model.bounding_box  # (x_min, y_min, x_max, y_max)
    x_min, y_min, x_max, y_max = bb

    # --- Horizontal dimensions (along bottom, below y_min) ---
    _add_horizontal_dims(
        sheet, model, floor,
        y_base=y_min,
        offset_first=offset_first,
        offset_step=offset_step,
        include_openings=include_openings,
    )

    # --- Vertical dimensions (along left, left of x_min) ---
    _add_vertical_dims(
        sheet, model, floor,
        x_base=x_min,
        offset_first=offset_first,
        offset_step=offset_step,
        include_openings=include_openings,
    )

    # --- Internal room dimensions ---
    if include_internal:
        _add_internal_dims(sheet, model, floor)

    logger.info("Auto-dimensioning complete")


def _add_horizontal_dims(
    sheet, model, floor: int,
    y_base: float,
    offset_first: float,
    offset_step: float,
    include_openings: bool,
) -> None:
    """Add horizontal dimension chains below the plan."""
    wall_xs = _wall_x_coords(model, floor)
    if len(wall_xs) < 2:
        return

    row = 0

    # Row 1: Opening dimensions (smallest segments, closest to object)
    if include_openings:
        all_xs = _collect_x_breakpoints(model, floor)
        if len(all_xs) > len(wall_xs):
            # Only add if there are opening breakpoints beyond wall endpoints
            points = [(x, y_base) for x in all_xs]
            offset = offset_first + offset_step * row
            sheet.add_chain_dim(points, offset=offset, angle=0, add_total=False)
            row += 1

    # Row 2: Wall segment dimensions
    if len(wall_xs) >= 2:
        points = [(x, y_base) for x in wall_xs]
        offset = offset_first + offset_step * row
        sheet.add_chain_dim(points, offset=offset, angle=0, add_total=False)
        row += 1

    # Row 3: Total dimension
    if len(wall_xs) >= 2:
        offset = offset_first + offset_step * row
        sheet.add_dimension(
            (wall_xs[0], y_base),
            (wall_xs[-1], y_base),
            offset=offset,
            angle=0,
        )


def _add_vertical_dims(
    sheet, model, floor: int,
    x_base: float,
    offset_first: float,
    offset_step: float,
    include_openings: bool,
) -> None:
    """Add vertical dimension chains to the left of the plan."""
    wall_ys = _wall_y_coords(model, floor)
    if len(wall_ys) < 2:
        return

    row = 0

    # Row 1: Opening dimensions
    if include_openings:
        all_ys = _collect_y_breakpoints(model, floor)
        if len(all_ys) > len(wall_ys):
            points = [(x_base, y) for y in all_ys]
            offset = offset_first + offset_step * row
            sheet.add_chain_dim(points, offset=offset, angle=90, add_total=False)
            row += 1

    # Row 2: Wall segment dimensions
    if len(wall_ys) >= 2:
        points = [(x_base, y) for y in wall_ys]
        offset = offset_first + offset_step * row
        sheet.add_chain_dim(points, offset=offset, angle=90, add_total=False)
        row += 1

    # Row 3: Total dimension
    if len(wall_ys) >= 2:
        offset = offset_first + offset_step * row
        sheet.add_dimension(
            (x_base, wall_ys[0]),
            (x_base, wall_ys[-1]),
            offset=offset,
            angle=90,
        )


def _add_internal_dims(sheet, model, floor: int = 0) -> None:
    """Add internal room dimensions.

    For each horizontal and vertical internal wall, add a dimension
    showing the room width/depth it creates.
    """
    walls = model.walls_on_floor(floor)
    bb = model.bounding_box
    x_min, y_min, x_max, y_max = bb

    internal_h_dims: Set[Tuple[float, float, float]] = set()
    internal_v_dims: Set[Tuple[float, float, float]] = set()

    for w in walls:
        if w.is_structural:
            continue  # Only internal (non-structural) walls

        dx = abs(w.p2[0] - w.p1[0])
        dy = abs(w.p2[1] - w.p1[1])

        if dy < SNAP_TOL and dx > SNAP_TOL:
            # Horizontal internal wall — measure vertical spans it creates
            y_wall = _snap(w.p1[1])
            x_mid = (w.p1[0] + w.p2[0]) / 2
            # Find the Y values this wall divides between
            wall_ys = _wall_y_coords(model, floor)
            for i in range(len(wall_ys) - 1):
                if wall_ys[i] < y_wall < wall_ys[i + 1]:
                    # Dimension from wall_ys[i] to y_wall
                    key1 = (_snap(x_mid), wall_ys[i], y_wall)
                    key2 = (_snap(x_mid), y_wall, wall_ys[i + 1])
                    internal_v_dims.add(key1)
                    internal_v_dims.add(key2)

        elif dx < SNAP_TOL and dy > SNAP_TOL:
            # Vertical internal wall — measure horizontal spans
            x_wall = _snap(w.p1[0])
            y_mid = (w.p1[1] + w.p2[1]) / 2
            wall_xs = _wall_x_coords(model, floor)
            for i in range(len(wall_xs) - 1):
                if wall_xs[i] < x_wall < wall_xs[i + 1]:
                    key1 = (_snap(y_mid), wall_xs[i], x_wall)
                    key2 = (_snap(y_mid), x_wall, wall_xs[i + 1])
                    internal_h_dims.add(key1)
                    internal_h_dims.add(key2)

    # Draw internal horizontal dims (above internal walls)
    for y_mid, x1, x2 in internal_h_dims:
        sheet.add_dimension((x1, y_mid), (x2, y_mid), offset=0.3, angle=0)

    # Draw internal vertical dims (right of internal walls)
    for x_mid, y1, y2 in internal_v_dims:
        sheet.add_dimension((x_mid, y1), (x_mid, y2), offset=0.3, angle=90)


def auto_dimension_section(
    sheet,
    model,
    origin: Tuple[float, float] = (0.0, 0.0),
    floor: int = 0,
) -> None:
    """Add automatic level marks and height dimensions to a section.

    Adds:
    - Floor level mark (±0.00)
    - Ceiling height
    - Total building height
    - Sill and lintel heights for openings
    """
    ox, oy = origin
    bb = model.bounding_box
    x_min, y_min, x_max, y_max = bb
    ch = model.ceiling_height

    # Vertical dimension: floor to ceiling
    sheet.add_dimension(
        (ox + x_max + 0.3, oy),
        (ox + x_max + 0.3, oy + ch),
        offset=0.5,
        angle=90,
    )

    # Level marks as text
    th = 0.10
    mark_x = ox + x_max + 1.2

    # Floor level
    sheet.add_text((mark_x, oy), "\u00B10,00", height=th)

    # Ceiling level
    sheet.add_text(
        (mark_x, oy + ch),
        f"+{ch:.2f}".replace(".", ","),
        height=th,
    )

    # Total height (with roof)
    total_h = model.total_height_m
    if total_h > ch + 0.1:
        sheet.add_dimension(
            (ox + x_max + 0.3, oy),
            (ox + x_max + 0.3, oy + total_h),
            offset=1.0,
            angle=90,
        )
        sheet.add_text(
            (mark_x + 0.5, oy + total_h),
            f"+{total_h:.2f}".replace(".", ","),
            height=th,
        )

    # Foundation depth
    if model.foundation:
        fd = model.foundation.depth_m
        sheet.add_text(
            (mark_x, oy - fd),
            f"-{fd:.2f}".replace(".", ","),
            height=th,
        )
