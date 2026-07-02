"""Revision diff service — compares original output with engineer's revised DXF.

Learns from the differences:
- Shores ADDED by engineer = areas where script under-shored
- Shores REMOVED by engineer = areas where script over-shored
- Shores MOVED = spacing/positioning calibration
- New elements on VIGAS_DET/LAJES_DET = missed structural elements
"""

import math
import logging
from typing import List, Dict, Tuple

import ezdxf

logger = logging.getLogger(__name__)

# Matching tolerance — two shores within this distance are "the same"
MATCH_TOLERANCE = 0.30  # m


def _extract_shores(dxf_path: str, layer: str) -> List[Tuple[float, float, float]]:
    """Extract circle centers from a specific layer. Returns [(x, y, radius)]."""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    shores = []
    for entity in msp:
        if entity.dxftype() == "CIRCLE" and entity.dxf.layer == layer:
            cx = entity.dxf.center.x
            cy = entity.dxf.center.y
            r = entity.dxf.radius
            shores.append((cx, cy, r))
    return shores


def _match_shores(
    original: List[Tuple[float, float, float]],
    revised: List[Tuple[float, float, float]],
) -> Dict[str, list]:
    """Match shores between original and revised DXF.

    Returns dict with:
    - matched: [(orig_idx, rev_idx, distance)]
    - added: [rev_idx]  — in revised but not original (engineer added)
    - removed: [orig_idx]  — in original but not revised (engineer removed)
    """
    used_orig = set()
    used_rev = set()
    matched = []

    # Greedy nearest-neighbor matching
    pairs = []
    for ri, (rx, ry, _) in enumerate(revised):
        for oi, (ox, oy, _) in enumerate(original):
            dist = math.hypot(rx - ox, ry - oy)
            if dist <= MATCH_TOLERANCE:
                pairs.append((dist, oi, ri))

    pairs.sort()
    for dist, oi, ri in pairs:
        if oi in used_orig or ri in used_rev:
            continue
        matched.append((oi, ri, dist))
        used_orig.add(oi)
        used_rev.add(ri)

    added = [ri for ri in range(len(revised)) if ri not in used_rev]
    removed = [oi for oi in range(len(original)) if oi not in used_orig]

    return {"matched": matched, "added": added, "removed": removed}


def analyze_revision(original_dxf: str, revised_dxf: str) -> Dict:
    """Compare original output with engineer's revision.

    Returns a structured diff with learnings.
    """
    learnings = []

    # Compare beam shores
    orig_beam = _extract_shores(original_dxf, "ESCORAS_VIGA")
    rev_beam = _extract_shores(revised_dxf, "ESCORAS_VIGA")
    beam_diff = _match_shores(orig_beam, rev_beam)

    # Compare slab shores
    orig_slab = _extract_shores(original_dxf, "ESCORAS_LAJE")
    rev_slab = _extract_shores(revised_dxf, "ESCORAS_LAJE")
    slab_diff = _match_shores(orig_slab, rev_slab)

    # Beam shore changes
    if beam_diff["added"]:
        positions = [(rev_beam[i][0], rev_beam[i][1]) for i in beam_diff["added"]]
        learnings.append(
            f"Engenheiro ADICIONOU {len(beam_diff['added'])} escoras de viga — "
            f"areas sub-escoradas detectadas"
        )
        logger.info(f"Beam shores added: {positions}")

    if beam_diff["removed"]:
        positions = [(orig_beam[i][0], orig_beam[i][1]) for i in beam_diff["removed"]]
        learnings.append(
            f"Engenheiro REMOVEU {len(beam_diff['removed'])} escoras de viga — "
            f"areas sobre-escoradas ou redundantes"
        )
        logger.info(f"Beam shores removed: {positions}")

    # Slab shore changes
    if slab_diff["added"]:
        learnings.append(
            f"Engenheiro ADICIONOU {len(slab_diff['added'])} escoras de laje"
        )

    if slab_diff["removed"]:
        learnings.append(
            f"Engenheiro REMOVEU {len(slab_diff['removed'])} escoras de laje"
        )

    # Movement analysis (matched but not at same position)
    moved_beams = [(d, orig_beam[oi], rev_beam[ri])
                   for oi, ri, d in beam_diff["matched"] if d > 0.05]
    if moved_beams:
        avg_move = sum(d for d, _, _ in moved_beams) / len(moved_beams)
        learnings.append(
            f"Engenheiro REPOSICIONOU {len(moved_beams)} escoras de viga "
            f"(deslocamento medio: {avg_move:.2f}m)"
        )

    # Summary stats
    summary = {
        "beam_shores_original": len(orig_beam),
        "beam_shores_revised": len(rev_beam),
        "beam_added": len(beam_diff["added"]),
        "beam_removed": len(beam_diff["removed"]),
        "beam_moved": len(moved_beams),
        "beam_unchanged": len(beam_diff["matched"]) - len(moved_beams),
        "slab_shores_original": len(orig_slab),
        "slab_shores_revised": len(rev_slab),
        "slab_added": len(slab_diff["added"]),
        "slab_removed": len(slab_diff["removed"]),
        "learnings": learnings,
        "accuracy_beam": (
            len(beam_diff["matched"]) / max(len(orig_beam), 1) * 100
        ),
        "accuracy_slab": (
            len(slab_diff["matched"]) / max(len(orig_slab), 1) * 100
        ),
    }

    return summary
