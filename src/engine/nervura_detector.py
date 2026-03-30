"""Detect nervura (waffle/ribbed slab) rib grid and place shores on ribs.

Nervura slabs have a concave underside — shores can only be placed on the
rib lines (borders between caixões), not in the middle of the hollow panels.

Algorithm:
1. Identify the nervura region from densely packed small rects
2. Extract rib grid lines by finding aligned edges of the rects
3. Place shores at rib intersections and along rib lines
"""

import math
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

from shapely.geometry import Polygon, box

logger = logging.getLogger(__name__)

# Nervura detection thresholds
MIN_NERVURA_RECTS = 20      # Minimum rects to consider a nervura pattern
MAX_NERVURA_RECT_AREA = 2.0  # m² — individual rib fill max area
NN_TIGHT_THRESHOLD = 0.50   # m — NN distance below which rects are "densely packed"
NN_TIGHT_RATIO = 0.50       # >50% of rects must be densely packed

# Rib grid extraction
EDGE_SNAP_TOLERANCE = 0.15  # m — snap nearby edges to same grid line
MIN_RECTS_PER_LINE = 3      # Minimum rects aligned to form a rib line

# Shore spacing on ribs
MAX_SHORE_SPACING_ON_RIB = 1.30  # m — max spacing along a rib line
MIN_SHORE_SPACING = 0.40    # m — minimum spacing between shores


@dataclass
class NervuraRegion:
    """Detected nervura slab region with rib grid."""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    h_rib_lines: List[float]  # Y coordinates of horizontal rib lines
    v_rib_lines: List[float]  # X coordinates of vertical rib lines
    area_m2: float

    @property
    def polygon(self) -> Polygon:
        return box(self.x_min, self.y_min, self.x_max, self.y_max)


@dataclass
class RibShorePosition:
    """A shore position on a nervura rib."""
    x: float
    y: float
    rib_direction: str  # 'H' or 'V' or 'intersection'


def detect_nervura_regions(
    rects: List[dict],
    beams: list,
) -> List[NervuraRegion]:
    """Detect nervura slab regions from densely packed small rects.

    Args:
        rects: List of rect dicts with cx, cy, width, height, area, layer.
        beams: Classified beam elements (to define structural bounds).

    Returns:
        List of NervuraRegion with rib grid information.
    """
    if len(rects) < MIN_NERVURA_RECTS:
        return []

    # Compute structural bounding box from beams — only consider rects
    # within this area (filters out cross-section details, legends, etc.)
    beam_xs = []
    beam_ys = []
    for b in beams:
        if hasattr(b, 'geometry') and len(b.geometry) >= 2:
            for pt in b.geometry:
                beam_xs.append(pt[0])
                beam_ys.append(pt[1])
    if not beam_xs:
        return []

    struct_margin = 2.0  # m — margin around beam bounding box
    struct_x_min = min(beam_xs) - struct_margin
    struct_x_max = max(beam_xs) + struct_margin
    struct_y_min = min(beam_ys) - struct_margin
    struct_y_max = max(beam_ys) + struct_margin

    # Group rects by layer, filtered to structural area
    by_layer = {}
    for r in rects:
        if not (struct_x_min <= r["cx"] <= struct_x_max and
                struct_y_min <= r["cy"] <= struct_y_max):
            continue
        layer = r.get("layer", "")
        by_layer.setdefault(layer, []).append(r)

    regions = []

    for layer, layer_rects in by_layer.items():
        # Filter to small rects only
        small_rects = [r for r in layer_rects
                       if r["area"] <= MAX_NERVURA_RECT_AREA and r["area"] > 0.001]
        if len(small_rects) < MIN_NERVURA_RECTS:
            continue

        # Check density — nervura rects are tightly packed
        positions = [(r["cx"], r["cy"]) for r in small_rects]
        tight_count = 0
        for i, (x1, y1) in enumerate(positions):
            min_dist = 999.0
            for j, (x2, y2) in enumerate(positions):
                if i == j:
                    continue
                d = math.hypot(x1 - x2, y1 - y2)
                if d < min_dist:
                    min_dist = d
            if min_dist < NN_TIGHT_THRESHOLD:
                tight_count += 1

        if tight_count / len(small_rects) < NN_TIGHT_RATIO:
            continue  # Not densely packed enough

        # This layer is nervura — extract rib grid
        region = _extract_rib_grid(small_rects, beams)
        if region:
            logger.info(
                f"Nervura detected on layer '{layer}': "
                f"{len(small_rects)} rects, "
                f"{len(region.h_rib_lines)} H ribs, "
                f"{len(region.v_rib_lines)} V ribs, "
                f"area {region.area_m2:.1f}m²"
            )
            regions.append(region)

    return regions


def _extract_rib_grid(
    rects: List[dict],
    beams: list,
) -> Optional[NervuraRegion]:
    """Extract H/V rib grid lines from nervura rect edges.

    Ribs are the borders between caixões. We find them by clustering
    the edges (x_min, x_max, y_min, y_max) of the nervura rects into
    aligned grid lines.
    """
    # Bounding box of the nervura region
    all_cx = [r["cx"] for r in rects]
    all_cy = [r["cy"] for r in rects]
    region_x_min = min(all_cx) - 0.5
    region_x_max = max(all_cx) + 0.5
    region_y_min = min(all_cy) - 0.5
    region_y_max = max(all_cy) + 0.5

    # Collect all horizontal edges (y-coordinates of rect top/bottom)
    h_edges = []
    v_edges = []
    for r in rects:
        w = r["width"]
        h = r["height"]
        if w < 0.05 or h < 0.05:
            continue  # Skip degenerate rects
        h_edges.append(r["cy"] - h / 2)  # bottom
        h_edges.append(r["cy"] + h / 2)  # top
        v_edges.append(r["cx"] - w / 2)  # left
        v_edges.append(r["cx"] + w / 2)  # right

    # Cluster edges into grid lines
    h_rib_lines = _cluster_values(h_edges, EDGE_SNAP_TOLERANCE, MIN_RECTS_PER_LINE)
    v_rib_lines = _cluster_values(v_edges, EDGE_SNAP_TOLERANCE, MIN_RECTS_PER_LINE)

    # Also add beam axes as rib lines (beams are the main ribs)
    for beam in beams:
        if not hasattr(beam, 'geometry') or len(beam.geometry) < 2:
            continue
        s, e = beam.geometry[0], beam.geometry[1]
        dx = abs(e[0] - s[0])
        dy = abs(e[1] - s[1])
        mid_x = (s[0] + e[0]) / 2
        mid_y = (s[1] + e[1]) / 2

        # Only add beams within the nervura region
        if not (region_x_min <= mid_x <= region_x_max and
                region_y_min <= mid_y <= region_y_max):
            continue

        if dx >= dy:  # H beam -> adds a Y rib line
            h_rib_lines.append(mid_y)
        else:  # V beam -> adds an X rib line
            v_rib_lines.append(mid_x)

    # Deduplicate rib lines (merge lines within tolerance)
    h_rib_lines = _cluster_values(h_rib_lines, EDGE_SNAP_TOLERANCE * 2, 1)
    v_rib_lines = _cluster_values(v_rib_lines, EDGE_SNAP_TOLERANCE * 2, 1)

    if not h_rib_lines and not v_rib_lines:
        return None

    area = (region_x_max - region_x_min) * (region_y_max - region_y_min)

    return NervuraRegion(
        x_min=region_x_min,
        x_max=region_x_max,
        y_min=region_y_min,
        y_max=region_y_max,
        h_rib_lines=sorted(h_rib_lines),
        v_rib_lines=sorted(v_rib_lines),
        area_m2=area,
    )


def _cluster_values(
    values: List[float],
    tolerance: float,
    min_count: int,
) -> List[float]:
    """Cluster numeric values into representative lines.

    Groups values within `tolerance` of each other, keeps clusters
    with at least `min_count` members, returns the mean of each cluster.
    """
    if not values:
        return []

    sorted_vals = sorted(values)
    clusters = []
    current_cluster = [sorted_vals[0]]

    for v in sorted_vals[1:]:
        if v - current_cluster[-1] <= tolerance:
            current_cluster.append(v)
        else:
            clusters.append(current_cluster)
            current_cluster = [v]
    clusters.append(current_cluster)

    return [
        sum(c) / len(c)
        for c in clusters
        if len(c) >= min_count
    ]


def distribute_nervura_shores(
    region: NervuraRegion,
    max_spacing: float = MAX_SHORE_SPACING_ON_RIB,
    pillar_positions: Optional[List[Tuple[float, float]]] = None,
    pillar_margin: float = 0.30,
) -> List[RibShorePosition]:
    """Place shores along nervura rib lines.

    Shores are placed:
    1. At all rib intersections (H rib × V rib)
    2. Along rib lines between intersections if spacing > max_spacing

    Args:
        region: Detected nervura region with rib grid.
        max_spacing: Maximum spacing between shores along a rib.
        pillar_positions: List of (x, y) pillar centers to exclude.
        pillar_margin: Minimum distance from a pillar to place a shore.
    """
    pillar_positions = pillar_positions or []
    shores = []
    placed = set()  # Track (rounded_x, rounded_y) to avoid duplicates

    def _is_near_pillar(x: float, y: float) -> bool:
        for px, py in pillar_positions:
            if math.hypot(x - px, y - py) < pillar_margin:
                return True
        return False

    def _try_place(x: float, y: float, direction: str) -> bool:
        key = (round(x, 2), round(y, 2))
        if key in placed:
            return False
        if _is_near_pillar(x, y):
            return False
        if not (region.x_min <= x <= region.x_max and
                region.y_min <= y <= region.y_max):
            return False
        placed.add(key)
        shores.append(RibShorePosition(x=x, y=y, rib_direction=direction))
        return True

    # 1. Place shores at all rib intersections
    for y_rib in region.h_rib_lines:
        for x_rib in region.v_rib_lines:
            _try_place(x_rib, y_rib, "intersection")

    # 2. Along H rib lines (between V rib intersections)
    for y_rib in region.h_rib_lines:
        v_lines = sorted(region.v_rib_lines)
        # Also add region boundaries
        all_x = [region.x_min] + v_lines + [region.x_max]
        for k in range(len(all_x) - 1):
            x_start = all_x[k]
            x_end = all_x[k + 1]
            span = x_end - x_start
            if span <= max_spacing:
                continue  # Already covered by intersection shores
            n_extra = int(math.ceil(span / max_spacing)) - 1
            if n_extra <= 0:
                continue
            step = span / (n_extra + 1)
            for j in range(1, n_extra + 1):
                _try_place(x_start + j * step, y_rib, "H")

    # 3. Along V rib lines (between H rib intersections)
    for x_rib in region.v_rib_lines:
        h_lines = sorted(region.h_rib_lines)
        all_y = [region.y_min] + h_lines + [region.y_max]
        for k in range(len(all_y) - 1):
            y_start = all_y[k]
            y_end = all_y[k + 1]
            span = y_end - y_start
            if span <= max_spacing:
                continue
            n_extra = int(math.ceil(span / max_spacing)) - 1
            if n_extra <= 0:
                continue
            step = span / (n_extra + 1)
            for j in range(1, n_extra + 1):
                _try_place(x_rib, y_start + j * step, "V")

    logger.info(
        f"Nervura shores: {len(shores)} "
        f"({sum(1 for s in shores if s.rib_direction == 'intersection')} intersections, "
        f"{sum(1 for s in shores if s.rib_direction == 'H')} on H ribs, "
        f"{sum(1 for s in shores if s.rib_direction == 'V')} on V ribs)"
    )

    return shores
