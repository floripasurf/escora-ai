"""Geometric classification of DXF segments into structural elements.

Beams: parallel line pairs with small gap (= beam width), long length.
Pillars: small closed rectangles (area < MAX_PILLAR_AREA).
"""

from dataclasses import dataclass
from typing import List

MAX_BEAM_WIDTH = 0.50
MIN_BEAM_WIDTH = 0.08
MAX_PILLAR_AREA = 0.50
MIN_PILLAR_AREA = 0.015  # m² — filter hatching/fill SOLIDs
MIN_PILLAR_DIM = 0.10  # m — NBR minimum for structural columns
MIN_BEAM_LENGTH_DEFAULT = 0.50


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
            score = min(0.95, 0.50 + 0.05 * min(length_ratio, 9))

            beams.append(BeamCandidate(
                axis_coord=axis_x, start=overlap_start, end=overlap_end,
                width_m=gap, length_m=overlap_len, direction="y", score=score,
            ))

    return beams


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
        if aspect > 4.0:
            continue
        # Deduplicate: round center to 1cm precision
        key = (round(r["cx"], 2), round(r["cy"], 2))
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
