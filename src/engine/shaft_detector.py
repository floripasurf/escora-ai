"""Detect shaft/void regions (elevator shafts, pipe openings) in structural plans.

Shafts are floor openings that should NOT receive shoring because there is no
slab to support. In DXF files, shafts are typically marked by:

1. **X patterns**: Two diagonal lines crossing inside a rectangular region
2. **Text labels**: "POÇO", "ELEVADOR", "FURO", "VAZIO", "SHAFT", "DUTO"
3. **Layer names**: Layers containing "ABER", "FURO", "SHAFT", "POCO", "VAZIO"

This module detects shaft regions and returns exclusion polygons that prevent
slab shores from being placed inside them.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from shapely.geometry import Polygon, Point, box

logger = logging.getLogger(__name__)

# Shaft size constraints (m²) — real-world shaft areas
MIN_SHAFT_AREA = 0.5    # Smallest pipe opening worth excluding
MAX_SHAFT_AREA = 50.0   # Largest elevator shaft / stairwell group

# Aspect ratio limits for shaft rectangles
MAX_SHAFT_ASPECT = 4.0  # Shafts are roughly square; aspect > 4 is likely a beam

# X-pattern matching tolerances
X_CENTER_TOLERANCE_RATIO = 0.25  # Centers must be within 25% of diagonal length
X_LENGTH_RATIO_MIN = 0.5        # Shorter diagonal must be >= 50% of longer
X_ANGLE_MIN = 15.0              # Minimum angle from horizontal/vertical (degrees)
X_ANGLE_MAX = 75.0              # Maximum angle

# Text proximity to shaft center (m)
TEXT_SHAFT_PROXIMITY = 3.0

# Layer keywords indicating shaft/opening
SHAFT_LAYER_KEYWORDS = {
    "aber", "furo", "shaft", "poco", "poço", "vazio",
    "elev", "duto", "abertura", "opening",
}

# Text keywords indicating shaft/opening
# Note: "FURO" alone matches too many false positives (e.g., "FUROS NA ALVENARIA")
# so we require it at word boundary or as part of specific patterns
SHAFT_TEXT_KEYWORDS = {
    "POÇO", "POCO", "ELEVADOR", "VAZIO", "SHAFT",
    "DUTO", "ABERTURA", "OPENING", "ELEV.",
}

# Regex-style patterns that need word-boundary matching
SHAFT_TEXT_PATTERNS_EXACT = {
    "FURO F",   # "FURO F1", "FURO F2", etc.
    "FURO %%",  # "FURO %%C18" (diameter symbol)
    "FURO D",   # "FURO D=", etc.
}


@dataclass
class ShaftRegion:
    """A detected shaft/void region."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    area_m2: float
    detection_method: str  # "x_pattern", "text", "layer"
    confidence: float = 0.8
    label: Optional[str] = None

    @property
    def polygon(self) -> Polygon:
        return box(self.x_min, self.y_min, self.x_max, self.y_max)

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x_min + self.x_max) / 2, (self.y_min + self.y_max) / 2)

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min


def _is_shaft_layer_name(layer: str) -> bool:
    lower = (layer or "").lower()
    return any(kw in lower for kw in SHAFT_LAYER_KEYWORDS)


def _is_shaft_text_content(content: str) -> bool:
    content_upper = (content or "").upper().strip()
    for kw in SHAFT_TEXT_KEYWORDS:
        if kw in content_upper:
            return True
    for pattern in SHAFT_TEXT_PATTERNS_EXACT:
        if pattern in content_upper:
            return True
    return False


def _line_angle_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    """Angle of line from horizontal, in degrees (0-90)."""
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    if dx < 1e-9 and dy < 1e-9:
        return 0.0
    return abs(math.degrees(math.atan2(dy, dx)))


def _line_slope_sign(x1: float, y1: float, x2: float, y2: float) -> int:
    """Return +1 for upward slope (/), -1 for downward (\\), 0 for flat."""
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-9:
        return 0
    slope = dy / dx
    if slope > 0.1:
        return 1
    elif slope < -0.1:
        return -1
    return 0


def _line_length(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _line_center(x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _line_bbox(x1: float, y1: float, x2: float, y2: float):
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def detect_shafts_from_x_patterns(
    diagonals: list,
    scale: float = 1.0,
) -> List[ShaftRegion]:
    """Detect shaft regions from X-pattern diagonal lines.

    Finds pairs of diagonal lines that:
    - Cross near each other (centers within tolerance)
    - Have similar lengths
    - Are at diagonal angles (not H/V)
    - Form a bounding box of shaft-appropriate size

    Args:
        diagonals: List of DiagonalEntity objects with x1,y1,x2,y2,layer
        scale: Coordinate scale factor
    """
    if not diagonals:
        return []

    # Filter to truly diagonal lines (not near-H or near-V)
    diagonal_lines = []
    for d in diagonals:
        angle = _line_angle_deg(d.x1, d.y1, d.x2, d.y2)
        length = _line_length(d.x1, d.y1, d.x2, d.y2) * scale
        if length < 0.3:  # Too short to be shaft marker
            continue
        if X_ANGLE_MIN <= angle <= X_ANGLE_MAX:
            diagonal_lines.append(d)

    if len(diagonal_lines) < 2:
        return []

    # Find pairs that form X patterns
    used = set()
    shafts = []

    for i, d1 in enumerate(diagonal_lines):
        if i in used:
            continue
        c1 = _line_center(d1.x1, d1.y1, d1.x2, d1.y2)
        l1 = _line_length(d1.x1, d1.y1, d1.x2, d1.y2) * scale

        best_j = None
        best_dist = float("inf")

        for j, d2 in enumerate(diagonal_lines):
            if j <= i or j in used:
                continue

            c2 = _line_center(d2.x1, d2.y1, d2.x2, d2.y2)
            l2 = _line_length(d2.x1, d2.y1, d2.x2, d2.y2) * scale

            # Centers must be close
            center_dist = math.hypot(
                (c1[0] - c2[0]) * scale, (c1[1] - c2[1]) * scale
            )
            max_center_dist = max(l1, l2) * X_CENTER_TOLERANCE_RATIO
            if center_dist > max_center_dist:
                continue

            # Similar lengths
            ratio = min(l1, l2) / max(l1, l2) if max(l1, l2) > 0 else 0
            if ratio < X_LENGTH_RATIO_MIN:
                continue

            # Slopes must differ: one "/" and one "\" to form an X
            s1 = _line_slope_sign(d1.x1, d1.y1, d1.x2, d1.y2)
            s2 = _line_slope_sign(d2.x1, d2.y1, d2.x2, d2.y2)
            if s1 == s2:  # Same slope direction = parallel, not X
                continue

            if center_dist < best_dist:
                best_dist = center_dist
                best_j = j

        if best_j is None:
            continue

        d2 = diagonal_lines[best_j]
        used.add(i)
        used.add(best_j)

        # Compute bounding box of the X pattern
        all_x = [d1.x1, d1.x2, d2.x1, d2.x2]
        all_y = [d1.y1, d1.y2, d2.y1, d2.y2]
        x_min = min(all_x) * scale
        y_min = min(all_y) * scale
        x_max = max(all_x) * scale
        y_max = max(all_y) * scale

        w = x_max - x_min
        h = y_max - y_min
        area = w * h

        # Validate shaft dimensions
        if area < MIN_SHAFT_AREA or area > MAX_SHAFT_AREA:
            continue
        aspect = max(w, h) / min(w, h) if min(w, h) > 0.01 else 99
        if aspect > MAX_SHAFT_ASPECT:
            continue

        shafts.append(ShaftRegion(
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            area_m2=area, detection_method="x_pattern", confidence=0.90,
        ))

    return shafts


def detect_shafts_from_text(
    texts: list,
    scale: float = 1.0,
) -> List[ShaftRegion]:
    """Detect shaft regions from text labels.

    Looks for text containing shaft keywords and creates a small exclusion
    zone around the text position. These are typically paired with X patterns
    but can also appear alone.

    Args:
        texts: List of TextEntity objects with content, x, y, layer
        scale: Coordinate scale factor
    """
    shafts = []
    for t in texts:
        content_upper = t.content.upper().strip()
        if not _is_shaft_text_content(content_upper):
            continue

        # Create a default shaft region around the text
        # Text position is usually at the center or edge of the shaft
        cx = t.x * scale
        cy = t.y * scale
        # Default shaft size: 1.5m x 1.5m (conservative)
        half = 0.75
        shafts.append(ShaftRegion(
            x_min=cx - half, y_min=cy - half,
            x_max=cx + half, y_max=cy + half,
            area_m2=half * half * 4,
            detection_method="text", confidence=0.70,
            label=content_upper,
        ))

    return shafts


def detect_shafts_from_layers(
    hatches: list,
    polylines: list,
    scale: float = 1.0,
) -> List[ShaftRegion]:
    """Detect shaft regions from entities on shaft-specific layers.

    Looks for hatches and closed polylines on layers containing shaft keywords
    like "ABER" (abertura), "FURO", "SHAFT", etc.

    Args:
        hatches: List of HatchEntity objects
        polylines: List of PolylineEntity objects
        scale: Coordinate scale factor
    """
    shafts = []

    # Check hatches on shaft layers
    for h in hatches:
        layer = getattr(h, "layer", "") if not isinstance(h, dict) else h.get("layer", "")
        if not _is_shaft_layer_name(layer):
            continue

        points = getattr(h, "points", []) if not isinstance(h, dict) else h.get("points", [])
        if len(points) < 3:
            continue

        xs = [p[0] * scale for p in points]
        ys = [p[1] * scale for p in points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        w = x_max - x_min
        h_dim = y_max - y_min
        area = w * h_dim

        if MIN_SHAFT_AREA <= area <= MAX_SHAFT_AREA:
            aspect = max(w, h_dim) / min(w, h_dim) if min(w, h_dim) > 0.01 else 99
            if aspect <= MAX_SHAFT_ASPECT:
                shafts.append(ShaftRegion(
                    x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
                    area_m2=area, detection_method="layer", confidence=0.85,
                ))

    # Check closed polylines on shaft layers
    for pl in polylines:
        layer = getattr(pl, "layer", "") if not isinstance(pl, dict) else pl.get("layer", "")
        is_closed = getattr(pl, "is_closed", False) if not isinstance(pl, dict) else pl.get("is_closed", False)
        if not is_closed or not _is_shaft_layer_name(layer):
            continue

        points = getattr(pl, "points", []) if not isinstance(pl, dict) else pl.get("points", [])
        if len(points) < 3:
            continue

        xs = [p[0] * scale for p in points]
        ys = [p[1] * scale for p in points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        w = x_max - x_min
        h_dim = y_max - y_min
        area = w * h_dim

        if MIN_SHAFT_AREA <= area <= MAX_SHAFT_AREA:
            aspect = max(w, h_dim) / min(w, h_dim) if min(w, h_dim) > 0.01 else 99
            if aspect <= MAX_SHAFT_ASPECT:
                shafts.append(ShaftRegion(
                    x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
                    area_m2=area, detection_method="layer", confidence=0.85,
                ))

    return shafts


def _merge_nearby_shafts(
    shafts: List[ShaftRegion],
    merge_distance: float = 0.5,
) -> List[ShaftRegion]:
    """Merge overlapping or very close shaft regions.

    Text-detected shafts are often near X-pattern shafts for the same opening.
    This merges them into a single region, keeping the highest confidence.
    """
    if len(shafts) <= 1:
        return shafts

    merged = []
    used = set()

    for i, s1 in enumerate(shafts):
        if i in used:
            continue

        group = [s1]
        used.add(i)

        for j, s2 in enumerate(shafts):
            if j in used or j <= i:
                continue

            # Check overlap or proximity
            cx1, cy1 = s1.center
            cx2, cy2 = s2.center
            dist = math.hypot(cx1 - cx2, cy1 - cy2)

            # Also check bounding box overlap
            overlap_x = s1.x_max >= s2.x_min - merge_distance and s2.x_max >= s1.x_min - merge_distance
            overlap_y = s1.y_max >= s2.y_min - merge_distance and s2.y_max >= s1.y_min - merge_distance

            if overlap_x and overlap_y:
                group.append(s2)
                used.add(j)

        # Merge group into single region
        x_min = min(s.x_min for s in group)
        y_min = min(s.y_min for s in group)
        x_max = max(s.x_max for s in group)
        y_max = max(s.y_max for s in group)
        best_confidence = max(s.confidence for s in group)
        best_method = max(group, key=lambda s: s.confidence).detection_method
        label = next((s.label for s in group if s.label), None)

        merged.append(ShaftRegion(
            x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max,
            area_m2=(x_max - x_min) * (y_max - y_min),
            detection_method=best_method,
            confidence=best_confidence,
            label=label,
        ))

    return merged


def detect_all_shafts(
    diagonals: list,
    texts: list,
    hatches: list,
    polylines: list,
    scale: float = 1.0,
) -> List[ShaftRegion]:
    """Run all 3 shaft detection strategies and merge results.

    Args:
        diagonals: DiagonalEntity list from parser
        texts: TextEntity list from parser
        hatches: HatchEntity list from parser
        polylines: PolylineEntity list from parser
        scale: Coordinate scale factor

    Returns:
        List of ShaftRegion exclusion zones.
    """
    all_shafts = []

    # Strategy 1: X patterns (highest confidence)
    x_shafts = detect_shafts_from_x_patterns(diagonals, scale)
    all_shafts.extend(x_shafts)

    # Strategy 2: Text labels
    text_shafts = detect_shafts_from_text(texts, scale)
    all_shafts.extend(text_shafts)

    # Strategy 3: Layer-based
    layer_shafts = detect_shafts_from_layers(hatches, polylines, scale)
    all_shafts.extend(layer_shafts)

    if not all_shafts:
        return []

    # Merge nearby/overlapping detections
    merged = _merge_nearby_shafts(all_shafts)

    # Post-merge size filter: merging can create regions exceeding MAX_SHAFT_AREA
    merged = [s for s in merged if s.area_m2 <= MAX_SHAFT_AREA]

    if merged:
        methods = {}
        for s in merged:
            methods[s.detection_method] = methods.get(s.detection_method, 0) + 1
        method_str = ", ".join(f"{v} via {k}" for k, v in methods.items())
        total_area = sum(s.area_m2 for s in merged)
        logger.info(
            f"Shaft detection: {len(merged)} void regions "
            f"({method_str}), total area {total_area:.1f}m²"
        )

    return merged


def subtract_shafts_from_slabs(
    slab_polygons: list,
    shaft_regions: List[ShaftRegion],
    buffer_m: float = 0.05,
) -> list:
    """Cut shaft holes from slab polygons instead of removing whole slabs.

    When a small shaft sits inside a large slab, the slab keeps its boundary
    but gets a hole where the shaft is. This prevents shores from being
    placed inside shaft voids while preserving the surrounding slab.

    Args:
        slab_polygons: List of Shapely Polygon objects (slab panels).
        shaft_regions: Detected shaft regions.
        buffer_m: Small buffer around shaft polygons for clean cuts.

    Returns:
        Updated list of slab polygons (some may now have holes).
    """
    if not shaft_regions or not slab_polygons:
        return slab_polygons

    from shapely.geometry import MultiPolygon
    from shapely.validation import make_valid

    shaft_polys = [s.polygon.buffer(buffer_m) for s in shaft_regions]
    result = []

    def _polygon_parts(geom):
        if geom is None or geom.is_empty:
            return []
        if isinstance(geom, Polygon):
            return [geom] if geom.area >= 0.5 else []
        if isinstance(geom, MultiPolygon):
            return [g for g in geom.geoms if g.area >= 0.5]
        if hasattr(geom, "geoms"):
            return [
                g for g in geom.geoms
                if isinstance(g, Polygon) and g.area >= 0.5
            ]
        return []

    for slab in slab_polygons:
        parts = [slab]
        for sp in shaft_polys:
            next_parts = []
            for part in parts:
                try:
                    if not part.intersects(sp):
                        next_parts.append(part)
                        continue
                    diff = part.difference(sp)
                    if diff.is_empty:
                        continue
                    if not diff.is_valid:
                        diff = make_valid(diff)
                    next_parts.extend(_polygon_parts(diff))
                except Exception:
                    next_parts.append(part)
            parts = _polygon_parts(MultiPolygon(next_parts)) if next_parts else []
            if not parts:
                break
        result.extend(parts)

    return result


def filter_slab_polygons_by_shafts(
    slab_polygons: list,
    shaft_regions: List[ShaftRegion],
    overlap_threshold: float = 0.30,
) -> Tuple[list, List[int]]:
    """Remove slab polygons that overlap significantly with shaft regions.

    Args:
        slab_polygons: List of Shapely Polygon objects (slab panels)
        shaft_regions: Detected shaft regions
        overlap_threshold: Minimum overlap ratio to consider slab as shaft

    Returns:
        (filtered_polygons, removed_indices)
    """
    if not shaft_regions or not slab_polygons:
        return slab_polygons, []

    shaft_polys = [s.polygon for s in shaft_regions]
    filtered = []
    removed = []

    for i, slab in enumerate(slab_polygons):
        is_shaft = False
        for sp in shaft_polys:
            try:
                intersection = slab.intersection(sp)
                overlap = intersection.area / slab.area if slab.area > 0 else 0
                if overlap >= overlap_threshold:
                    is_shaft = True
                    break
            except Exception:
                continue

        if is_shaft:
            removed.append(i)
        else:
            filtered.append(slab)

    return filtered, removed
