"""Filter drawing regions: separate main plan from detail views, sections, title blocks.

Real structural DXFs contain multiple views at different scales:
- Main floor plan (largest region, what we want)
- Detail views ("DETALHE", "DET.", scale 1:20 or 1:25)
- Cross-sections ("CORTE", "SEÇÃO", "SEC.")
- Title block (bottom-right, "CARIMBO")

This module identifies the main plan region and filters out detail/section entities
to prevent false beam/pillar detection from annotation-scale geometry.
"""

import math
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
from src.pipeline.stage_parse import (
    TextEntity, SegmentEntity, RectEntity, CircleEntity,
    PolylineEntity, HatchEntity, DimensionEntity,
)

logger = logging.getLogger(__name__)

# Text patterns that indicate a detail/section view (not main plan)
DETAIL_KEYWORDS = [
    "DETALHE", "DET.", "DET ",
    "CORTE", "SEÇÃO", "SECAO", "SEC.",
    "VISTA", "ELEVAÇÃO", "ELEVACAO",
    "CARIMBO", "TÍTULO", "TITULO",
    "ESCALA", "NOTAS", "OBSERVAÇÕES",
    "LEGENDA", "QUADRO",
]

# Minimum area ratio: main plan must be at least this fraction of total extent
MIN_MAIN_AREA_RATIO = 0.3

# Margin expansion around detail text to exclude nearby entities
DETAIL_EXCLUSION_RADIUS = 3.0  # meters


@dataclass
class DrawingRegion:
    """A detected region within the drawing."""
    region_type: str  # "PLAN", "DETAIL", "SECTION", "TITLE"
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    label: str = ""


def _find_detail_regions(texts: List[TextEntity]) -> List[DrawingRegion]:
    """Find text annotations that indicate detail/section views."""
    regions = []
    for t in texts:
        content_upper = t.content.upper().strip()
        for keyword in DETAIL_KEYWORDS:
            if keyword in content_upper:
                regions.append(DrawingRegion(
                    region_type="DETAIL" if "DET" in keyword else "SECTION",
                    x_min=t.x - DETAIL_EXCLUSION_RADIUS,
                    x_max=t.x + DETAIL_EXCLUSION_RADIUS,
                    y_min=t.y - DETAIL_EXCLUSION_RADIUS,
                    y_max=t.y + DETAIL_EXCLUSION_RADIUS,
                    label=content_upper[:40],
                ))
                break
    return regions


def _point_in_any_region(x: float, y: float, regions: List[DrawingRegion]) -> bool:
    """Check if a point falls within any detail/section region."""
    for r in regions:
        if r.x_min <= x <= r.x_max and r.y_min <= y <= r.y_max:
            return True
    return False


def _segment_center(seg: SegmentEntity) -> Tuple[float, float]:
    """Get approximate center of a segment."""
    if seg.type == "H":
        return ((seg.x_min + seg.x_max) / 2, seg.y)
    else:
        return (seg.x, (seg.y_min + seg.y_max) / 2)


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
    """Filter out entities belonging to detail views, sections, and title blocks.

    Returns filtered lists + list of warning messages.
    """
    warnings = []
    detail_regions = _find_detail_regions(texts)

    if not detail_regions:
        return texts, segments, rects, circles, polylines, hatches, dimensions, warnings

    n_regions = len(detail_regions)
    warnings.append(
        f"Detectadas {n_regions} regiões de detalhe/corte — "
        f"filtrando entidades fora da planta principal"
    )

    # Filter each entity type by checking if its center falls in a detail region
    filtered_segments = [
        s for s in segments
        if not _point_in_any_region(*_segment_center(s), detail_regions)
    ]

    filtered_rects = [
        r for r in rects
        if not _point_in_any_region(r.cx, r.cy, detail_regions)
    ]

    filtered_circles = [
        c for c in circles
        if not _point_in_any_region(c.cx, c.cy, detail_regions)
    ]

    filtered_polylines = [
        p for p in polylines
        if not p.points or not _point_in_any_region(p.points[0][0], p.points[0][1], detail_regions)
    ]

    filtered_hatches = [
        h for h in hatches
        if not h.points or not _point_in_any_region(h.points[0][0], h.points[0][1], detail_regions)
    ]

    # Keep all texts and dimensions (useful for metadata extraction everywhere)
    filtered_texts = texts
    filtered_dimensions = dimensions

    removed = (
        len(segments) - len(filtered_segments)
        + len(rects) - len(filtered_rects)
        + len(circles) - len(filtered_circles)
    )
    if removed > 0:
        warnings.append(f"Filtradas {removed} entidades de regiões de detalhe/corte")
        logger.info(f"Region filter removed {removed} entities from detail/section views")

    return (
        filtered_texts, filtered_segments, filtered_rects,
        filtered_circles, filtered_polylines, filtered_hatches,
        filtered_dimensions, warnings,
    )
