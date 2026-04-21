"""Filter drawing regions: separate main plan from detail views, sections, title blocks.

Real structural DXFs contain multiple views at different scales:
- Main floor plan (largest region, what we want)
- Detail views ("DETALHE", "DET.", scale 1:20 or 1:25)
- Cross-sections ("CORTE", "SEÇÃO", "SEC.")
- Title block (bottom-right, "CARIMBO")

This module uses spatial clustering to identify the main plan region,
then filters out entities from secondary regions (sections, details, BOM).
"""

import logging
from typing import List, Tuple
from dataclasses import dataclass
from src.pipeline.stage_parse import (
    TextEntity, SegmentEntity, RectEntity, CircleEntity,
    PolylineEntity, HatchEntity, DimensionEntity,
)

logger = logging.getLogger(__name__)

# Text patterns that indicate a detail/section view (secondary pass)
DETAIL_KEYWORDS = [
    "DETALHE", "DET.", "DET ",
    "CORTE", "SEÇÃO", "SECAO", "SEC.",
    "VISTA", "ELEVAÇÃO", "ELEVACAO",
    "CARIMBO", "TÍTULO", "TITULO",
    "ESCALA", "NOTAS", "OBSERVAÇÕES",
    "LEGENDA", "QUADRO",
    "PLANTA", "ESC ",
    "A-A", "B-B", "C-C", "D-D", "E-E",
]

DETAIL_EXCLUSION_RADIUS = 5.0  # meters (detail views typically span 3-8m)

# Layer name patterns that indicate detail/section views (not main plan)
DETAIL_LAYER_KEYWORDS = [
    "detalhe", "corte", "secao", "seção", "vista",
    "elevacao", "elevação", "carimbo",
]
REGION_MARGIN = 1.0  # meters of margin around main plan


@dataclass
class Region:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    count: int = 0


def _centroid_of_points(pts: List[Tuple[float, float]]) -> Tuple[float, float]:
    if not pts:
        return (0.0, 0.0)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _collect_centroids(
    segments: List[SegmentEntity],
    rects: List[RectEntity],
    circles: List[CircleEntity],
    polylines: List[PolylineEntity],
    hatches: List[HatchEntity],
) -> List[Tuple[float, float]]:
    """Collect centroid (x, y) of all geometric entities."""
    centroids: List[Tuple[float, float]] = []
    for s in segments:
        if s.type == "H":
            cx = (s.x_min + s.x_max) / 2
            cy = s.y
        else:  # V
            cx = s.x
            cy = (s.y_min + s.y_max) / 2
        centroids.append((cx, cy))
    for r in rects:
        centroids.append((r.cx, r.cy))
    for c in circles:
        centroids.append((c.cx, c.cy))
    for p in polylines:
        if p.points:
            centroids.append(_centroid_of_points(p.points))
    for h in hatches:
        if h.points:
            centroids.append(_centroid_of_points(h.points))
    return centroids


def _find_gap_splits(values: List[float], total_range: float) -> List[float]:
    """Find large gaps in sorted values that indicate region boundaries.

    Returns list of split points (midpoints of gaps).
    """
    if len(values) < 2:
        return []
    threshold = max(2.0, 0.02 * total_range)
    sorted_vals = sorted(values)
    splits = []
    for i in range(len(sorted_vals) - 1):
        gap = sorted_vals[i + 1] - sorted_vals[i]
        if gap > threshold:
            splits.append((sorted_vals[i] + sorted_vals[i + 1]) / 2)
    return splits


def _detect_regions(centroids: List[Tuple[float, float]]) -> List[Region]:
    """Detect rectangular regions via gap-based spatial clustering."""
    if not centroids:
        return []

    xs = [c[0] for c in centroids]
    ys = [c[1] for c in centroids]
    x_range = max(xs) - min(xs)
    y_range = max(ys) - min(ys)

    # Split along X axis
    x_splits = _find_gap_splits(xs, x_range)
    x_bounds = [min(xs)] + x_splits + [max(xs)]

    regions: List[Region] = []
    for i in range(len(x_bounds) - 1):
        x_lo, x_hi = x_bounds[i], x_bounds[i + 1]
        # Collect centroids in this X band
        band_pts = [(x, y) for x, y in centroids if x_lo <= x <= x_hi]
        if not band_pts:
            continue

        band_ys = [p[1] for p in band_pts]
        band_y_range = max(band_ys) - min(band_ys)

        # Split Y within this band
        y_splits = _find_gap_splits(band_ys, band_y_range)
        y_bounds_band = [min(band_ys)] + y_splits + [max(band_ys)]

        for j in range(len(y_bounds_band) - 1):
            y_lo, y_hi = y_bounds_band[j], y_bounds_band[j + 1]
            count = sum(1 for _, y in band_pts if y_lo <= y <= y_hi)
            if count > 0:
                regions.append(Region(x_lo, x_hi, y_lo, y_hi, count))

    return regions


def _point_in_region(x: float, y: float, r: Region, margin: float = 0.0) -> bool:
    return (r.x_min - margin <= x <= r.x_max + margin and
            r.y_min - margin <= y <= r.y_max + margin)


def _is_in_detail_zone(x: float, y: float, texts: List[TextEntity]) -> bool:
    """Secondary pass: check if point is near a detail/section keyword text."""
    for t in texts:
        content_upper = t.content.upper().strip()
        for kw in DETAIL_KEYWORDS:
            if kw in content_upper:
                if (abs(x - t.x) < DETAIL_EXCLUSION_RADIUS and
                        abs(y - t.y) < DETAIL_EXCLUSION_RADIUS):
                    return True
                break
    return False


def _detect_bounding_rectangles(
    polylines: List[PolylineEntity],
) -> List[Region]:
    """Detect closed rectangular polylines that frame detail/section views.

    Brazilian DXFs commonly use rectangular LWPOLYLINE frames around views
    labeled "CORTE A-A", "DETALHE 01", etc. These frames help identify
    secondary regions even when gap-based clustering fails.

    Returns list of Regions corresponding to detected bounding rectangles.
    """
    rects: List[Region] = []
    for p in polylines:
        pts = p.points if hasattr(p, "points") else []
        if not pts or len(pts) < 4:
            continue
        # Check if closed (first ≈ last)
        if abs(pts[0][0] - pts[-1][0]) > 0.1 or abs(pts[0][1] - pts[-1][1]) > 0.1:
            # Also accept 4-point polylines (implicitly closed)
            if len(pts) != 4:
                continue
        # Check rectangularity: 4 unique corners, axis-aligned edges
        corners = pts[:4]
        xs = sorted(set(round(c[0], 2) for c in corners))
        ys = sorted(set(round(c[1], 2) for c in corners))
        if len(xs) != 2 or len(ys) != 2:
            continue
        w = xs[1] - xs[0]
        h = ys[1] - ys[0]
        # Filter: too small → not a view frame; too large → the whole sheet
        if w < 1.0 or h < 1.0 or w > 50.0 or h > 50.0:
            continue
        # Check if layer suggests a frame/detail
        layer = getattr(p, "layer", "").lower()
        is_frame_layer = any(
            kw in layer for kw in ["quadro", "frame", "borda", "viewport"]
        )
        # Accept if it's on a frame layer OR has reasonable detail-view dimensions
        if is_frame_layer or (w < 20.0 and h < 20.0):
            rects.append(Region(xs[0], xs[1], ys[0], ys[1], count=0))
    return rects


def filter_main_plan(
    texts: List[TextEntity],
    segments: List[SegmentEntity],
    rects: List[RectEntity],
    circles: List[CircleEntity],
    polylines: List[PolylineEntity],
    hatches: List[HatchEntity],
    dimensions: List[DimensionEntity],
) -> Tuple[
    List[TextEntity], List[SegmentEntity], List[RectEntity],
    List[CircleEntity], List[PolylineEntity], List[HatchEntity],
    List[DimensionEntity], List[str],
]:
    """Filter entities to keep only the main structural plan region.

    Uses spatial clustering to detect separated drawing regions,
    selects the one with most entities as main plan, and filters
    out everything else. Applies keyword exclusion as secondary pass.
    """
    warnings: List[str] = []

    # Step 1: Collect centroids and detect regions
    centroids = _collect_centroids(segments, rects, circles, polylines, hatches)
    if not centroids:
        return texts, segments, rects, circles, polylines, hatches, dimensions, warnings

    regions = _detect_regions(centroids)

    # If only 1 region, no spatial filtering needed
    if len(regions) <= 1:
        logger.info("Region filter: single region detected, skipping spatial clustering")
        return texts, segments, rects, circles, polylines, hatches, dimensions, warnings

    # Step 2: Select main plan (region with most entities)
    total_entities = sum(r.count for r in regions)
    main = max(regions, key=lambda r: r.count)

    # Only activate filtering if main region clearly dominates (>35% of entities).
    # Lowered from 50% because detail views with many entities (hatches, dims)
    # can push the main region below 50%, disabling the filter entirely.
    if main.count < 0.35 * total_entities:
        logger.info(
            f"Region filter: {len(regions)} regions detected but main has only "
            f"{main.count}/{total_entities} ({main.count/total_entities:.0%}) — "
            f"treating as single-zone file"
        )
        return texts, segments, rects, circles, polylines, hatches, dimensions, warnings
    logger.info(
        f"Region filter: detected {len(regions)} regions. "
        f"Main plan: X=[{main.x_min:.0f}, {main.x_max:.0f}] "
        f"Y=[{main.y_min:.0f}, {main.y_max:.0f}] ({main.count} entities)"
    )
    for i, r in enumerate(regions):
        tag = " [MAIN]" if r is main else ""
        logger.info(
            f"  Region {i}: X=[{r.x_min:.0f}, {r.x_max:.0f}] "
            f"Y=[{r.y_min:.0f}, {r.y_max:.0f}] count={r.count}{tag}"
        )

    warnings.append(
        f"Detectadas {len(regions)} regiões no desenho — "
        f"planta principal: X=[{main.x_min:.0f}..{main.x_max:.0f}], "
        f"{main.count} entidades"
    )

    m = REGION_MARGIN

    # Step 2.5: Detect bounding rectangles that frame detail views
    detail_rects = _detect_bounding_rectangles(polylines)
    # Remove rectangles that overlap with the main region (they ARE the plan)
    detail_rects = [
        dr for dr in detail_rects
        if not _point_in_region(
            (dr.x_min + dr.x_max) / 2, (dr.y_min + dr.y_max) / 2, main, m
        )
    ]
    if detail_rects:
        logger.info(
            f"Region filter: {len(detail_rects)} bounding rectangles "
            f"detected as detail/section frames"
        )

    # Step 3: Filter entities — keep only those in main plan region
    def _seg_center(s: SegmentEntity) -> Tuple[float, float]:
        if s.type == "H":
            return ((s.x_min + s.x_max) / 2, s.y)
        return (s.x, (s.y_min + s.y_max) / 2)

    def _is_detail_layer(layer: str) -> bool:
        """Check if entity is on a detail/section layer."""
        lower = layer.lower().strip()
        return any(kw in lower for kw in DETAIL_LAYER_KEYWORDS)

    def _in_detail_rect(x: float, y: float) -> bool:
        return any(_point_in_region(x, y, dr) for dr in detail_rects)

    def _in_main(x: float, y: float, layer: str = "") -> bool:
        if not _point_in_region(x, y, main, m):
            return False
        if _in_detail_rect(x, y):
            return False
        if _is_in_detail_zone(x, y, texts):
            return False
        if layer and _is_detail_layer(layer):
            return False
        return True

    f_segments = [s for s in segments if _in_main(*_seg_center(s), getattr(s, 'layer', ''))]
    f_rects = [r for r in rects if _in_main(r.cx, r.cy, getattr(r, 'layer', ''))]
    f_circles = [c for c in circles if _in_main(c.cx, c.cy, getattr(c, 'layer', ''))]
    f_polylines = [
        p for p in polylines
        if p.points and _in_main(*_centroid_of_points(p.points), getattr(p, 'layer', ''))
    ]
    f_hatches = [
        h for h in hatches
        if h.points and _in_main(*_centroid_of_points(h.points), getattr(h, 'layer', ''))
    ]
    f_texts = [t for t in texts if _point_in_region(t.x, t.y, main, m)]
    f_dims = [d for d in dimensions if _point_in_region(d.x, d.y, main, m)]

    removed = (
        (len(segments) - len(f_segments))
        + (len(rects) - len(f_rects))
        + (len(circles) - len(f_circles))
        + (len(polylines) - len(f_polylines))
        + (len(hatches) - len(f_hatches))
    )
    if removed > 0:
        warnings.append(f"Filtradas {removed} entidades de regiões secundárias")
        logger.info(f"Region filter removed {removed} entities from secondary regions")

    return f_texts, f_segments, f_rects, f_circles, f_polylines, f_hatches, f_dims, warnings
