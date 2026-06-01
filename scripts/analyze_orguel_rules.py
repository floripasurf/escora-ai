"""Reverse-engineer shoring DECISION CRITERIA from Orguel PE DXF files.

Instead of computing medians (which flatten out the intelligence), this script
builds a dataset of per-entity observations with structural context, then
derives the rules Orguel engineers apply:

- When tower vs shore? (correlated with pillar proximity, beam intersection)
- How does spacing vary? (near pillars vs mid-span vs edges)
- Where do towers go on beams? (ends, mid, intersections)
- What's the VM pattern? (parallel/perpendicular to beams)

Output: data/analysis/orguel_rules_extracted.json with:
  - "entity_dataset": per-entity rows with context
  - "decision_rules": extracted if/then rules
  - "per_file": file-level summaries

Usage:
    python3 scripts/analyze_orguel_rules.py
"""

import sys
import os
import re
import json
import math
import logging
import argparse
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

import ezdxf
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layer classification
# ---------------------------------------------------------------------------
SHORE_LAYER_PATTERNS = {
    "telescopica": ["ESC310", "ESC360", "ESC450"],
    "torre": ["TORRE_VIGA", "TORRE_LAJE", "Torre_Laje", "Torre_Viga",
              "TA_Viga", "TA_Laje", "TOR_MANUAL"],
    "vm": ["VM130", "VM80", "VM50"],
    "cruzeta": ["CRUZETA", "CRUZ"],
}

STRUCTURAL_LAYER_PATTERNS = {
    "pilar": ["PILAR", "PIL_", "WP_PILAR"],
    "viga": ["VIGAS", "VIG_", "FORMA", "WP_EST"],
    "laje": ["LAJE", "WP_LAJES", "WP_TAG_LAJE"],
    "eixo": ["EIXO", "WP_EIXO"],
}

DEDUP_TOLERANCE_M = 0.05


def classify_layer(layer_name: str) -> Tuple[Optional[str], Optional[str]]:
    ln = layer_name.upper()
    for cat, patterns in SHORE_LAYER_PATTERNS.items():
        for p in patterns:
            if p.upper() in ln:
                sub = "viga" if "VIGA" in ln or "VIG" in ln else "laje"
                return cat, sub
    for cat, patterns in STRUCTURAL_LAYER_PATTERNS.items():
        for p in patterns:
            if p.upper() in ln:
                return cat, None
    return None, None


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class ShoringEntity:
    x: float
    y: float
    layer: str
    block_name: str
    rotation: float
    category: str       # telescopica, torre, vm, cruzeta
    subcategory: str    # laje, viga


@dataclass
class PillarEntity:
    x: float
    y: float
    width_m: float
    depth_m: float


@dataclass
class BeamAxis:
    x1: float
    y1: float
    x2: float
    y2: float
    layer: str

    @property
    def length(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)

    @property
    def midpoint(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def point_to_segment_distance(px, py, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-10:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def project_onto_segment(px, py, x1, y1, x2, y2) -> float:
    """Project point onto segment, return parameter t in [0,1]."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-10:
        return 0.5
    return max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))


def deduplicate_points(points, tolerance=DEDUP_TOLERANCE_M):
    if not points:
        return []
    unique = [points[0]]
    for p in points[1:]:
        if all(math.hypot(p[0] - u[0], p[1] - u[1]) > tolerance for u in unique):
            unique.append(p)
    return unique


# ---------------------------------------------------------------------------
# Coordinate detection
# ---------------------------------------------------------------------------
def detect_unit_scale(doc) -> float:
    msp = doc.modelspace()
    xs, ys = [], []
    count = 0
    for e in msp:
        if e.dxftype() == "LINE":
            xs.extend([e.dxf.start.x, e.dxf.end.x])
            ys.extend([e.dxf.start.y, e.dxf.end.y])
        elif e.dxftype() == "INSERT":
            xs.append(e.dxf.insert.x)
            ys.append(e.dxf.insert.y)
        count += 1
        if count > 500:
            break
    if not xs:
        return 0.01
    coord_range = max(max(xs) - min(xs), max(ys) - min(ys))
    return 0.01 if coord_range > 100 else 1.0


# ---------------------------------------------------------------------------
# Entity extraction (same as before — pillars, beams, shoring)
# ---------------------------------------------------------------------------
def extract_shoring_entities(doc, scale: float) -> List[ShoringEntity]:
    msp = doc.modelspace()
    entities = []
    for e in msp:
        if e.dxftype() != "INSERT":
            continue
        layer = e.dxf.layer
        cat, sub = classify_layer(layer)
        if cat is None or cat not in SHORE_LAYER_PATTERNS:
            continue
        x = e.dxf.insert.x * scale
        y = e.dxf.insert.y * scale
        rotation = getattr(e.dxf, 'rotation', 0.0)
        block_name = e.dxf.name
        bn_lower = block_name.lower()
        if any(skip in bn_lower for skip in [
            "esticador", "grampo", "suporte", "tubo", "cons710",
            "detalhe", "corte", "vista",
        ]):
            continue
        entities.append(ShoringEntity(
            x=x, y=y, layer=layer, block_name=block_name,
            rotation=rotation, category=cat, subcategory=sub,
        ))
    return entities


def extract_pillars(doc, scale: float) -> List[PillarEntity]:
    msp = doc.modelspace()
    pillars = []
    for e in msp:
        layer = e.dxf.layer
        cat, _ = classify_layer(layer)
        if cat != "pilar":
            continue
        etype = e.dxftype()
        if etype == "INSERT":
            x = e.dxf.insert.x * scale
            y = e.dxf.insert.y * scale
            w, d = 0.20, 0.20
            m = re.search(r"(\d+)[xX](\d+)", e.dxf.name)
            if m:
                w = float(m.group(1)) / 100.0
                d = float(m.group(2)) / 100.0
            pillars.append(PillarEntity(x=x, y=y, width_m=w, depth_m=d))
        elif etype == "SOLID":
            pts = [e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx2]
            cx = sum(p.x for p in pts) / 3 * scale
            cy = sum(p.y for p in pts) / 3 * scale
            pillars.append(PillarEntity(x=cx, y=cy, width_m=0.20, depth_m=0.20))
        elif etype == "LWPOLYLINE":
            try:
                pts = list(e.get_points(format="xy"))
                if len(pts) >= 3:
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    cx = (min(xs) + max(xs)) / 2 * scale
                    cy = (min(ys) + max(ys)) / 2 * scale
                    w = (max(xs) - min(xs)) * scale
                    d = (max(ys) - min(ys)) * scale
                    if 0.05 < w < 2.0 and 0.05 < d < 2.0:
                        pillars.append(PillarEntity(x=cx, y=cy, width_m=w, depth_m=d))
            except Exception:
                pass
        elif etype == "HATCH":
            try:
                paths = list(e.paths)
                if paths:
                    all_pts = []
                    for path in paths:
                        if hasattr(path, 'vertices'):
                            all_pts.extend(path.vertices)
                    if all_pts:
                        xs = [p[0] for p in all_pts]
                        ys = [p[1] for p in all_pts]
                        cx = (min(xs) + max(xs)) / 2 * scale
                        cy = (min(ys) + max(ys)) / 2 * scale
                        w = (max(xs) - min(xs)) * scale
                        d = (max(ys) - min(ys)) * scale
                        if 0.05 < w < 2.0 and 0.05 < d < 2.0:
                            pillars.append(PillarEntity(x=cx, y=cy, width_m=w, depth_m=d))
            except Exception:
                pass
    unique = []
    for p in pillars:
        if all(math.hypot(p.x - u.x, p.y - u.y) > 0.10 for u in unique):
            unique.append(p)
    return unique


def extract_beam_axes(doc, scale: float) -> List[BeamAxis]:
    msp = doc.modelspace()
    axes = []
    for e in msp:
        etype = e.dxftype()
        if etype not in ("LINE", "LWPOLYLINE"):
            continue
        layer = e.dxf.layer
        cat, _ = classify_layer(layer)
        if cat != "viga":
            continue
        if etype == "LINE":
            axes.append(BeamAxis(
                x1=e.dxf.start.x * scale, y1=e.dxf.start.y * scale,
                x2=e.dxf.end.x * scale, y2=e.dxf.end.y * scale,
                layer=layer,
            ))
        elif etype == "LWPOLYLINE":
            try:
                pts = list(e.get_points(format="xy"))
                for i in range(len(pts) - 1):
                    axes.append(BeamAxis(
                        x1=pts[i][0] * scale, y1=pts[i][1] * scale,
                        x2=pts[i+1][0] * scale, y2=pts[i+1][1] * scale,
                        layer=layer,
                    ))
            except Exception:
                pass
    return axes


# ---------------------------------------------------------------------------
# CONTEXT COMPUTATION — the core of the new analysis
# ---------------------------------------------------------------------------
def compute_entity_context(
    entity: ShoringEntity,
    pillars: List[PillarEntity],
    beams: List[BeamAxis],
    all_shoring: List[ShoringEntity],
) -> dict:
    """For a single shoring entity, compute its structural context.

    This is the key function: instead of aggregating, we produce one row
    per entity with all measurable context so we can find correlations.
    """
    ctx = {
        "x": round(entity.x, 3),
        "y": round(entity.y, 3),
        "category": entity.category,        # torre, telescopica, vm
        "subcategory": entity.subcategory,   # viga, laje
        "block_name": entity.block_name,
        "layer": entity.layer,
        "rotation": round(entity.rotation, 1),
    }

    # --- Distance to nearest pillar ---
    if pillars:
        dists = [math.hypot(entity.x - p.x, entity.y - p.y) for p in pillars]
        min_idx = int(np.argmin(dists))
        ctx["dist_to_pillar_m"] = round(dists[min_idx], 3)
        ctx["nearest_pillar_w"] = pillars[min_idx].width_m
        ctx["nearest_pillar_d"] = pillars[min_idx].depth_m
    else:
        ctx["dist_to_pillar_m"] = None

    # --- Distance to nearest beam axis + position along beam ---
    if beams:
        best_dist = float('inf')
        best_beam = None
        best_t = 0.5
        for b in beams:
            d = point_to_segment_distance(entity.x, entity.y,
                                          b.x1, b.y1, b.x2, b.y2)
            if d < best_dist:
                best_dist = d
                best_beam = b
                best_t = project_onto_segment(entity.x, entity.y,
                                              b.x1, b.y1, b.x2, b.y2)
        if best_beam and best_dist < 10.0:
            ctx["dist_to_beam_m"] = round(best_dist, 3)
            ctx["beam_length_m"] = round(best_beam.length, 3)
            ctx["position_on_beam_t"] = round(best_t, 3)  # 0=start, 1=end
            # Is this near a beam endpoint (= near a pillar/support)?
            ctx["near_beam_end"] = best_t < 0.10 or best_t > 0.90
            ctx["near_beam_quarter"] = best_t < 0.25 or best_t > 0.75
        else:
            ctx["dist_to_beam_m"] = None
            ctx["beam_length_m"] = None
            ctx["position_on_beam_t"] = None
            ctx["near_beam_end"] = None
            ctx["near_beam_quarter"] = None
    else:
        ctx["dist_to_beam_m"] = None
        ctx["beam_length_m"] = None
        ctx["position_on_beam_t"] = None
        ctx["near_beam_end"] = None
        ctx["near_beam_quarter"] = None

    # --- Is this at a beam-beam intersection? ---
    # Check if 2+ beam axes pass within 1m of this entity
    if beams:
        close_beams = [
            b for b in beams
            if point_to_segment_distance(entity.x, entity.y,
                                         b.x1, b.y1, b.x2, b.y2) < 1.0
        ]
        ctx["n_beams_within_1m"] = len(close_beams)
        ctx["at_beam_intersection"] = len(close_beams) >= 2
    else:
        ctx["n_beams_within_1m"] = 0
        ctx["at_beam_intersection"] = False

    # --- Nearest-neighbor distance (same category + subcategory) ---
    same_group = [
        e for e in all_shoring
        if e.category == entity.category
        and e.subcategory == entity.subcategory
        and (e.x != entity.x or e.y != entity.y)
        and math.hypot(e.x - entity.x, e.y - entity.y) > DEDUP_TOLERANCE_M
    ]
    if same_group:
        nn_dist = min(
            math.hypot(e.x - entity.x, e.y - entity.y) for e in same_group
        )
        ctx["nn_spacing_m"] = round(nn_dist, 3)
    else:
        ctx["nn_spacing_m"] = None

    return ctx


# ---------------------------------------------------------------------------
# Rule extraction from entity dataset
# ---------------------------------------------------------------------------
def extract_decision_rules(dataset: List[dict]) -> dict:
    """Analyze the entity dataset to find decision boundaries and rules."""
    rules = {}

    # Split by subcategory
    viga_entities = [d for d in dataset if d["subcategory"] == "viga"
                     and d["category"] in ("torre", "telescopica")]
    laje_entities = [d for d in dataset if d["subcategory"] == "laje"
                     and d["category"] in ("torre", "telescopica")]

    # =====================================================================
    # RULE 1: Tower vs Shore on BEAMS — when does Orguel choose tower?
    # =====================================================================
    if viga_entities:
        torre_viga = [d for d in viga_entities if d["category"] == "torre"]
        esc_viga = [d for d in viga_entities if d["category"] == "telescopica"]

        # 1a. Pillar proximity: do towers cluster near pillars?
        torre_pillar_dists = [d["dist_to_pillar_m"] for d in torre_viga
                              if d["dist_to_pillar_m"] is not None]
        esc_pillar_dists = [d["dist_to_pillar_m"] for d in esc_viga
                            if d["dist_to_pillar_m"] is not None]

        rules["beam_tower_vs_shore"] = {
            "n_towers": len(torre_viga),
            "n_shores": len(esc_viga),
            "tower_fraction": round(len(torre_viga) / max(1, len(viga_entities)), 3),
        }

        if torre_pillar_dists and esc_pillar_dists:
            rules["beam_tower_vs_shore"]["tower_dist_to_pillar"] = _stats(torre_pillar_dists)
            rules["beam_tower_vs_shore"]["shore_dist_to_pillar"] = _stats(esc_pillar_dists)
            rules["beam_tower_vs_shore"]["insight_pillar"] = (
                "Towers closer to pillars" if np.median(torre_pillar_dists) < np.median(esc_pillar_dists)
                else "Towers NOT preferentially near pillars"
            )

        # 1b. Beam intersections: do towers go at intersections?
        torre_at_intersect = sum(1 for d in torre_viga if d.get("at_beam_intersection"))
        esc_at_intersect = sum(1 for d in esc_viga if d.get("at_beam_intersection"))
        torre_intersect_pct = torre_at_intersect / max(1, len(torre_viga))
        esc_intersect_pct = esc_at_intersect / max(1, len(esc_viga))
        rules["beam_tower_vs_shore"]["tower_at_intersection_pct"] = round(torre_intersect_pct, 3)
        rules["beam_tower_vs_shore"]["shore_at_intersection_pct"] = round(esc_intersect_pct, 3)
        rules["beam_tower_vs_shore"]["insight_intersection"] = (
            f"Towers at beam intersections: {torre_intersect_pct:.0%} vs "
            f"shores: {esc_intersect_pct:.0%}"
        )

        # 1c. Position along beam: do towers go near ends or mid-span?
        torre_positions = [d["position_on_beam_t"] for d in torre_viga
                          if d["position_on_beam_t"] is not None]
        esc_positions = [d["position_on_beam_t"] for d in esc_viga
                        if d["position_on_beam_t"] is not None]
        if torre_positions:
            rules["beam_tower_vs_shore"]["tower_position_on_beam"] = _stats(torre_positions)
            torre_near_end_pct = sum(1 for t in torre_positions if t < 0.15 or t > 0.85) / len(torre_positions)
            rules["beam_tower_vs_shore"]["tower_near_beam_ends_pct"] = round(torre_near_end_pct, 3)
        if esc_positions:
            rules["beam_tower_vs_shore"]["shore_position_on_beam"] = _stats(esc_positions)

        # 1d. Beam length: do towers appear on longer beams?
        torre_beam_lengths = [d["beam_length_m"] for d in torre_viga
                             if d["beam_length_m"] is not None and d["beam_length_m"] > 0.5]
        esc_beam_lengths = [d["beam_length_m"] for d in esc_viga
                           if d["beam_length_m"] is not None and d["beam_length_m"] > 0.5]
        if torre_beam_lengths and esc_beam_lengths:
            rules["beam_tower_vs_shore"]["tower_beam_length"] = _stats(torre_beam_lengths)
            rules["beam_tower_vs_shore"]["shore_beam_length"] = _stats(esc_beam_lengths)

    # =====================================================================
    # RULE 2: Tower vs Shore on SLABS
    # =====================================================================
    if laje_entities:
        torre_laje = [d for d in laje_entities if d["category"] == "torre"]
        esc_laje = [d for d in laje_entities if d["category"] == "telescopica"]

        rules["slab_tower_vs_shore"] = {
            "n_towers": len(torre_laje),
            "n_shores": len(esc_laje),
            "tower_fraction": round(len(torre_laje) / max(1, len(laje_entities)), 3),
        }

        # 2a. Do slab towers cluster near beams (heavier load zone)?
        torre_beam_dists = [d["dist_to_beam_m"] for d in torre_laje
                           if d["dist_to_beam_m"] is not None]
        esc_beam_dists = [d["dist_to_beam_m"] for d in esc_laje
                         if d["dist_to_beam_m"] is not None]
        if torre_beam_dists and esc_beam_dists:
            rules["slab_tower_vs_shore"]["tower_dist_to_beam"] = _stats(torre_beam_dists)
            rules["slab_tower_vs_shore"]["shore_dist_to_beam"] = _stats(esc_beam_dists)
            rules["slab_tower_vs_shore"]["insight_beam_proximity"] = (
                "Slab towers closer to beams" if np.median(torre_beam_dists) < np.median(esc_beam_dists)
                else "Slab towers NOT preferentially near beams"
            )

        # 2b. Pillar distance
        torre_pillar = [d["dist_to_pillar_m"] for d in torre_laje
                       if d["dist_to_pillar_m"] is not None]
        esc_pillar = [d["dist_to_pillar_m"] for d in esc_laje
                     if d["dist_to_pillar_m"] is not None]
        if torre_pillar and esc_pillar:
            rules["slab_tower_vs_shore"]["tower_dist_to_pillar"] = _stats(torre_pillar)
            rules["slab_tower_vs_shore"]["shore_dist_to_pillar"] = _stats(esc_pillar)

    # =====================================================================
    # RULE 3: Spacing patterns (do they densify near supports?)
    # =====================================================================
    spacing_rules = {}

    for subcat, entities in [("viga", viga_entities), ("laje", laje_entities)]:
        if not entities:
            continue
        # Group by spacing AND distance-to-pillar
        with_both = [
            d for d in entities
            if d.get("nn_spacing_m") is not None
            and d.get("dist_to_pillar_m") is not None
        ]
        if len(with_both) < 10:
            continue

        # Split into near-pillar (< 2m) vs far-from-pillar (> 3m)
        near_pillar = [d for d in with_both if d["dist_to_pillar_m"] < 2.0]
        far_pillar = [d for d in with_both if d["dist_to_pillar_m"] > 3.0]

        if near_pillar and far_pillar:
            near_spacings = [d["nn_spacing_m"] for d in near_pillar]
            far_spacings = [d["nn_spacing_m"] for d in far_pillar]
            spacing_rules[subcat] = {
                "near_pillar_spacing": _stats(near_spacings),
                "far_pillar_spacing": _stats(far_spacings),
                "densifies_near_pillar": np.median(near_spacings) < np.median(far_spacings) * 0.85,
                "ratio": round(np.median(near_spacings) / max(0.01, np.median(far_spacings)), 3),
            }

        # For beams: spacing near beam-end vs mid-beam
        if subcat == "viga":
            near_end = [d for d in with_both
                       if d.get("near_beam_end") is True]
            mid_beam = [d for d in with_both
                       if d.get("near_beam_end") is False
                       and d.get("position_on_beam_t") is not None]
            if near_end and mid_beam:
                end_sp = [d["nn_spacing_m"] for d in near_end]
                mid_sp = [d["nn_spacing_m"] for d in mid_beam]
                spacing_rules[f"{subcat}_end_vs_mid"] = {
                    "near_beam_end_spacing": _stats(end_sp),
                    "mid_beam_spacing": _stats(mid_sp),
                    "densifies_near_ends": np.median(end_sp) < np.median(mid_sp) * 0.85,
                }

    rules["spacing_patterns"] = spacing_rules

    # =====================================================================
    # RULE 4: VM placement patterns
    # =====================================================================
    vm_entities = [d for d in dataset if d["category"] == "vm"]
    if vm_entities:
        vm_near_beam = [d for d in vm_entities
                       if d.get("dist_to_beam_m") is not None
                       and d["dist_to_beam_m"] < 2.0]
        rules["vm_patterns"] = {
            "total_vms": len(vm_entities),
            "vms_within_2m_of_beam": len(vm_near_beam),
            "pct_near_beam": round(len(vm_near_beam) / max(1, len(vm_entities)), 3),
        }
        # VM spacing by subcategory
        for subcat in ("viga", "laje"):
            vms = [d for d in vm_entities if d["subcategory"] == subcat
                   and d.get("nn_spacing_m") is not None]
            if vms:
                rules["vm_patterns"][f"spacing_{subcat}"] = _stats(
                    [d["nn_spacing_m"] for d in vms]
                )

    return rules


def _stats(values: list) -> dict:
    if not values:
        return {"count": 0}
    arr = np.array(values)
    return {
        "count": len(arr),
        "mean": round(float(np.mean(arr)), 3),
        "median": round(float(np.median(arr)), 3),
        "std": round(float(np.std(arr)), 3),
        "p10": round(float(np.percentile(arr, 10)), 3),
        "p25": round(float(np.percentile(arr, 25)), 3),
        "p75": round(float(np.percentile(arr, 75)), 3),
        "p90": round(float(np.percentile(arr, 90)), 3),
        "min": round(float(np.min(arr)), 3),
        "max": round(float(np.max(arr)), 3),
    }


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------
def analyze_file(filepath: str) -> Tuple[Optional[dict], List[dict]]:
    """Analyze a single Orguel DXF. Returns (file_summary, entity_rows)."""
    name = os.path.basename(filepath)
    logger.info(f"Analyzing: {name}")

    try:
        doc = ezdxf.readfile(filepath)
    except Exception as e:
        logger.error(f"  Failed: {e}")
        return None, []

    scale = detect_unit_scale(doc)
    logger.info(f"  Scale: {'cm→m (×0.01)' if scale < 0.1 else 'already m'}")

    shoring = extract_shoring_entities(doc, scale)
    pillars = extract_pillars(doc, scale)
    beams = extract_beam_axes(doc, scale)

    if not shoring:
        logger.warning(f"  No shoring entities found")
        return None, []

    # Deduplicate shoring by position
    seen_positions = set()
    unique_shoring = []
    for e in shoring:
        key = (round(e.x, 2), round(e.y, 2), e.category, e.subcategory)
        if key not in seen_positions:
            seen_positions.add(key)
            unique_shoring.append(e)
    shoring = unique_shoring

    logger.info(f"  Shoring: {len(shoring)} (deduped), Pillars: {len(pillars)}, Beams: {len(beams)}")

    # Compute context for each entity
    entity_rows = []
    for e in shoring:
        if e.category in ("telescopica", "torre", "vm"):
            ctx = compute_entity_context(e, pillars, beams, shoring)
            ctx["file"] = name
            entity_rows.append(ctx)

    # File summary
    counts = Counter((e.category, e.subcategory) for e in shoring)
    n_torre_viga = counts.get(("torre", "viga"), 0)
    n_torre_laje = counts.get(("torre", "laje"), 0)
    n_esc_viga = counts.get(("telescopica", "viga"), 0)
    n_esc_laje = counts.get(("telescopica", "laje"), 0)

    summary = {
        "filename": name,
        "n_pillars": len(pillars),
        "n_beams": len(beams),
        "torre_viga": n_torre_viga,
        "torre_laje": n_torre_laje,
        "esc_viga": n_esc_viga,
        "esc_laje": n_esc_laje,
        "vm130": counts.get(("vm", "laje"), 0) + counts.get(("vm", "viga"), 0),
        "tower_fraction_viga": round(n_torre_viga / max(1, n_torre_viga + n_esc_viga), 3),
        "tower_fraction_laje": round(n_torre_laje / max(1, n_torre_laje + n_esc_laje), 3),
    }

    logger.info(
        f"  T_viga:{n_torre_viga} E_viga:{n_esc_viga} "
        f"T_laje:{n_torre_laje} E_laje:{n_esc_laje}"
    )

    return summary, entity_rows


# ---------------------------------------------------------------------------
# Pretty-print rules
# ---------------------------------------------------------------------------
def print_rules(rules: dict):
    print(f"\n{'='*70}")
    print("  EXTRACTED DECISION RULES")
    print(f"{'='*70}")

    # Beam tower vs shore
    r = rules.get("beam_tower_vs_shore", {})
    if r:
        print(f"\n--- BEAMS: Tower vs Shore ---")
        print(f"  Total: {r.get('n_towers',0)} towers + {r.get('n_shores',0)} shores "
              f"(fraction: {r.get('tower_fraction',0):.0%})")
        if "insight_pillar" in r:
            print(f"  Pillar proximity: {r['insight_pillar']}")
            if "tower_dist_to_pillar" in r:
                tp = r["tower_dist_to_pillar"]
                sp = r["shore_dist_to_pillar"]
                print(f"    Tower→pillar: median {tp['median']:.2f}m (p25={tp['p25']:.2f}, p75={tp['p75']:.2f})")
                print(f"    Shore→pillar: median {sp['median']:.2f}m (p25={sp['p25']:.2f}, p75={sp['p75']:.2f})")
        if "insight_intersection" in r:
            print(f"  Beam intersections: {r['insight_intersection']}")
        if "tower_near_beam_ends_pct" in r:
            print(f"  Towers near beam ends (t<0.15 or t>0.85): {r['tower_near_beam_ends_pct']:.0%}")
        if "tower_beam_length" in r and "shore_beam_length" in r:
            tl = r["tower_beam_length"]
            sl = r["shore_beam_length"]
            print(f"  Beams with towers: median length {tl['median']:.2f}m")
            print(f"  Beams with shores: median length {sl['median']:.2f}m")

    # Slab tower vs shore
    r = rules.get("slab_tower_vs_shore", {})
    if r:
        print(f"\n--- SLABS: Tower vs Shore ---")
        print(f"  Total: {r.get('n_towers',0)} towers + {r.get('n_shores',0)} shores "
              f"(fraction: {r.get('tower_fraction',0):.0%})")
        if "insight_beam_proximity" in r:
            print(f"  Beam proximity: {r['insight_beam_proximity']}")
            if "tower_dist_to_beam" in r:
                tb = r["tower_dist_to_beam"]
                sb = r["shore_dist_to_beam"]
                print(f"    Tower→beam: median {tb['median']:.2f}m")
                print(f"    Shore→beam: median {sb['median']:.2f}m")

    # Spacing patterns
    sp = rules.get("spacing_patterns", {})
    if sp:
        print(f"\n--- SPACING PATTERNS ---")
        for key, data in sp.items():
            print(f"  {key}:")
            if "near_pillar_spacing" in data:
                ns = data["near_pillar_spacing"]
                fs = data["far_pillar_spacing"]
                densify = data.get("densifies_near_pillar", False)
                ratio = data.get("ratio", 1.0)
                print(f"    Near pillar (<2m): median {ns['median']:.2f}m")
                print(f"    Far from pillar (>3m): median {fs['median']:.2f}m")
                print(f"    Densification: {'YES' if densify else 'NO'} (ratio: {ratio:.2f})")
            if "near_beam_end_spacing" in data:
                es = data["near_beam_end_spacing"]
                ms = data["mid_beam_spacing"]
                densify = data.get("densifies_near_ends", False)
                print(f"    Near beam ends: median {es['median']:.2f}m")
                print(f"    Mid-beam: median {ms['median']:.2f}m")
                print(f"    End densification: {'YES' if densify else 'NO'}")

    # VM patterns
    vm = rules.get("vm_patterns", {})
    if vm:
        print(f"\n--- VM PATTERNS ---")
        print(f"  Total VMs: {vm.get('total_vms', 0)}")
        print(f"  Within 2m of beam: {vm.get('pct_near_beam', 0):.0%}")
        for key in ("spacing_viga", "spacing_laje"):
            if key in vm:
                s = vm[key]
                print(f"  {key}: median {s['median']:.2f}m (p25={s['p25']:.2f}, p75={s['p75']:.2f})")

    print(f"\n{'='*70}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Extract Orguel shoring decision rules")
    parser.add_argument("--files", type=str, default=None)
    parser.add_argument("--output", type=str, default="data/analysis/orguel_rules_extracted.json")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    if args.files:
        import glob
        files = sorted(glob.glob(args.files))
    else:
        orguel_dir = project_root / "input" / "orguel"
        files = sorted(str(f) for f in orguel_dir.glob("*.dxf"))

    if not files:
        logger.error("No DXF files found")
        sys.exit(1)

    files.sort(key=lambda f: os.path.getsize(f))

    print("=" * 70)
    print("  ESCORA.AI — Orguel Decision Rules Extraction")
    print("=" * 70)

    all_summaries = []
    all_entity_rows = []

    for filepath in files:
        summary, rows = analyze_file(filepath)
        if summary:
            all_summaries.append(summary)
            all_entity_rows.extend(rows)

    if not all_entity_rows:
        logger.error("No entities extracted")
        sys.exit(1)

    logger.info(f"\nTotal entity observations: {len(all_entity_rows)}")

    # Extract rules from the full dataset
    rules = extract_decision_rules(all_entity_rows)

    # Build output
    output = {
        "decision_rules": rules,
        "per_file": all_summaries,
        "entity_count": len(all_entity_rows),
        # Save a sample of the entity dataset (first 200 per category for inspection)
        "entity_sample": {
            "torre_viga": [d for d in all_entity_rows
                          if d["category"] == "torre" and d["subcategory"] == "viga"][:200],
            "esc_viga": [d for d in all_entity_rows
                        if d["category"] == "telescopica" and d["subcategory"] == "viga"][:200],
            "torre_laje": [d for d in all_entity_rows
                          if d["category"] == "torre" and d["subcategory"] == "laje"][:200],
            "esc_laje": [d for d in all_entity_rows
                        if d["category"] == "telescopica" and d["subcategory"] == "laje"][:200],
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _json_default(o):
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        raise TypeError(f"Not JSON serializable: {type(o)}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=_json_default)

    logger.info(f"Results saved to {output_path}")

    print_rules(rules)


if __name__ == "__main__":
    main()
