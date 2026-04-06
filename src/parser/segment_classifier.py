"""Geometric classification of DXF segments into structural elements.

Beams: parallel line pairs with small gap (= beam width), long length.
Pillars: small closed rectangles (area < MAX_PILLAR_AREA).
"""

from dataclasses import dataclass
from typing import List

MAX_BEAM_WIDTH = 0.65  # m — allows beams up to 60cm wide (NBR 6118)
MIN_BEAM_WIDTH = 0.08
MIN_BEAM_LENGTH_RATIO = 5.0  # length/width — real beams are elongated
MAX_PILLAR_AREA = 1.00  # m² — allows large columns (e.g. 0.87x0.94m)
MIN_PILLAR_AREA = 0.015  # m² — filter hatching/fill SOLIDs
MIN_PILLAR_DIM = 0.14  # m — NBR 6118 min is 19cm; 14cm filters dimension symbols
                        # (level triangles, tick marks) which are typically 10-12cm
MAX_PILLAR_ASPECT = 4.0  # aspect ratio — filters elongated dimension/annotation rects
PILLAR_CLUSTER_TOLERANCE = 0.30  # m — merge pillar SOLIDs within 30cm (same pillar has 2-3 SOLID fills)
MIN_BEAM_LENGTH_DEFAULT = 1.0  # m — real beams are at least 1m
BEAM_AXIS_TOLERANCE = 0.50  # m — group beams with similar axis coordinates
BEAM_SPAN_GAP_TOLERANCE = 0.05  # m — only merge truly overlapping spans, NOT across pillars


@dataclass
class BeamCandidate:
    axis_coord: float
    start: float
    end: float
    width_m: float
    length_m: float
    direction: str
    score: float = 0.0


@dataclass
class PillarCandidate:
    cx: float
    cy: float
    width_m: float
    depth_m: float
    score: float = 0.0


def find_beam_candidates(
    segments: List[dict],
    min_length: float = MIN_BEAM_LENGTH_DEFAULT,
) -> List[BeamCandidate]:
    h_segs = sorted(
        [s for s in segments if s["type"] == "H"],
        key=lambda s: s["y"],
    )
    v_segs = sorted(
        [s for s in segments if s["type"] == "V"],
        key=lambda s: s["x"],
    )

    beams = []

    # Sorted by Y, so we can break early when gap exceeds MAX_BEAM_WIDTH
    for i in range(len(h_segs)):
        for j in range(i + 1, len(h_segs)):
            gap = abs(h_segs[j]["y"] - h_segs[i]["y"])
            if gap > MAX_BEAM_WIDTH:
                break  # sorted — all subsequent j will have larger gap
            if gap < MIN_BEAM_WIDTH:
                continue
            overlap_start = max(h_segs[i]["x_min"], h_segs[j]["x_min"])
            overlap_end = min(h_segs[i]["x_max"], h_segs[j]["x_max"])
            overlap_len = overlap_end - overlap_start
            if overlap_len < min_length:
                continue

            axis_y = (h_segs[i]["y"] + h_segs[j]["y"]) / 2
            length_ratio = overlap_len / gap
            if length_ratio < MIN_BEAM_LENGTH_RATIO - 0.01:
                continue
            score = min(0.95, 0.50 + 0.05 * min(length_ratio, 9))

            beams.append(BeamCandidate(
                axis_coord=axis_y, start=overlap_start, end=overlap_end,
                width_m=gap, length_m=overlap_len, direction="x", score=score,
            ))

    # Sorted by X, so we can break early when gap exceeds MAX_BEAM_WIDTH
    for i in range(len(v_segs)):
        for j in range(i + 1, len(v_segs)):
            gap = abs(v_segs[j]["x"] - v_segs[i]["x"])
            if gap > MAX_BEAM_WIDTH:
                break
            if gap < MIN_BEAM_WIDTH:
                continue
            overlap_start = max(v_segs[i]["y_min"], v_segs[j]["y_min"])
            overlap_end = min(v_segs[i]["y_max"], v_segs[j]["y_max"])
            overlap_len = overlap_end - overlap_start
            if overlap_len < min_length:
                continue

            axis_x = (v_segs[i]["x"] + v_segs[j]["x"]) / 2
            length_ratio = overlap_len / gap
            if length_ratio < MIN_BEAM_LENGTH_RATIO - 0.01:
                continue
            score = min(0.95, 0.50 + 0.05 * min(length_ratio, 9))

            beams.append(BeamCandidate(
                axis_coord=axis_x, start=overlap_start, end=overlap_end,
                width_m=gap, length_m=overlap_len, direction="y", score=score,
            ))

    # Deduplicate overlapping beams: merge candidates with same axis and overlapping spans
    beams = _deduplicate_beams(beams)

    return beams


def _deduplicate_beams(beams: List[BeamCandidate]) -> List[BeamCandidate]:
    """Merge beam candidates that overlap on the same axis."""
    if not beams:
        return beams

    # Group by direction and axis coordinate (within tolerance)
    # Sort by axis to cluster nearby axes together
    beams_sorted = sorted(beams, key=lambda b: (b.direction, b.axis_coord))
    groups: list = []
    for b in beams_sorted:
        placed = False
        for g in groups:
            if g[0].direction == b.direction and abs(g[0].axis_coord - b.axis_coord) <= BEAM_AXIS_TOLERANCE:
                g.append(b)
                placed = True
                break
        if not placed:
            groups.append([b])

    result = []
    for group in groups:
        # Sort by start position
        group.sort(key=lambda b: b.start)
        # Merge spans that overlap or are separated by ≤ pillar width
        merged = group[0]
        for b in group[1:]:
            if b.start <= merged.end + BEAM_SPAN_GAP_TOLERANCE:  # bridge pillar gaps
                # Extend the merged beam
                merged = BeamCandidate(
                    axis_coord=merged.axis_coord,
                    start=min(merged.start, b.start),
                    end=max(merged.end, b.end),
                    width_m=(merged.width_m + b.width_m) / 2,
                    length_m=max(merged.end, b.end) - min(merged.start, b.start),
                    direction=merged.direction,
                    score=max(merged.score, b.score),
                )
            else:
                result.append(merged)
                merged = b
        result.append(merged)

    return result


MIN_CENTERLINE_LENGTH = 2.5  # m — minimum length for centerline beams
MAX_CENTERLINE_LENGTH = 20.0  # m — maximum length (longer = grid/dimension line)
DEFAULT_CENTERLINE_WIDTH = 0.14  # m — assumed width when no pair available


def find_centerline_beam_candidates(
    segments: List[dict],
    existing_beams: List[BeamCandidate] = None,
    min_length: float = MIN_CENTERLINE_LENGTH,
) -> List[BeamCandidate]:
    """Detect beam centerlines: single H/V segments that are beam axes.

    Some DXFs represent beams as single lines (centerlines/eixos) rather
    than parallel pairs. This function finds long H/V segments that don't
    overlap with already-detected parallel-pair beams.

    Args:
        segments: Segment dicts with x, y, x_min, y_min, x_max, y_max, type.
        existing_beams: Already detected parallel-pair beams to avoid duplicates.
        min_length: Minimum segment length to consider.

    Returns:
        List of BeamCandidate with default width.
    """
    existing_beams = existing_beams or []

    h_segs = [s for s in segments if s["type"] == "H"]
    v_segs = [s for s in segments if s["type"] == "V"]
    candidates = []

    for s in h_segs:
        length = s["x_max"] - s["x_min"]
        if length < min_length or length > MAX_CENTERLINE_LENGTH:
            continue
        axis_y = s["y"]
        if _overlaps_existing(axis_y, s["x_min"], s["x_max"], "x", existing_beams):
            continue
        candidates.append(BeamCandidate(
            axis_coord=axis_y,
            start=s["x_min"], end=s["x_max"],
            width_m=DEFAULT_CENTERLINE_WIDTH,
            length_m=length,
            direction="x",
            score=0.40,  # lower confidence than parallel-pair beams
        ))

    for s in v_segs:
        length = s["y_max"] - s["y_min"]
        if length < min_length or length > MAX_CENTERLINE_LENGTH:
            continue
        axis_x = s["x"]
        if _overlaps_existing(axis_x, s["y_min"], s["y_max"], "y", existing_beams):
            continue
        candidates.append(BeamCandidate(
            axis_coord=axis_x,
            start=s["y_min"], end=s["y_max"],
            width_m=DEFAULT_CENTERLINE_WIDTH,
            length_m=length,
            direction="y",
            score=0.40,
        ))

    return _deduplicate_beams(candidates)


def _overlaps_existing(
    axis: float, start: float, end: float,
    direction: str, existing: List[BeamCandidate],
    axis_tol: float = 1.0,
) -> bool:
    """Check if a centerline overlaps an existing parallel-pair beam."""
    for b in existing:
        if b.direction != direction:
            continue
        if abs(b.axis_coord - axis) > axis_tol:
            continue
        # Check span overlap
        overlap = min(end, b.end) - max(start, b.start)
        if overlap > 0.5 * (end - start):
            return True
    return False


def find_pillar_candidates(
    rects: List[dict],
    max_area: float = MAX_PILLAR_AREA,
) -> List[PillarCandidate]:
    pillars = []
    seen = set()  # deduplicate overlapping rects
    for r in rects:
        if r["area"] > max_area or r["area"] < MIN_PILLAR_AREA:
            continue
        if min(r["width"], r["height"]) < MIN_PILLAR_DIM:
            continue
        aspect = max(r["width"], r["height"]) / max(min(r["width"], r["height"]), 0.01)
        if aspect > MAX_PILLAR_ASPECT:
            continue
        # Deduplicate: round center to 5cm precision (multiple SOLIDs per pillar)
        key = (round(r["cx"] / PILLAR_CLUSTER_TOLERANCE) * PILLAR_CLUSTER_TOLERANCE,
               round(r["cy"] / PILLAR_CLUSTER_TOLERANCE) * PILLAR_CLUSTER_TOLERANCE)
        if key in seen:
            continue
        seen.add(key)
        score = min(0.90, 0.60 + 0.10 * (1.0 / max(aspect, 1.0)))
        pillars.append(PillarCandidate(
            cx=r["cx"], cy=r["cy"],
            width_m=r["width"], depth_m=r["height"],
            score=score,
        ))
    return pillars
