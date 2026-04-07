"""Stage 3: Combined geometric + textual classification.

Combines geometric signal (parallel pairs, small rects) with textual signal
(layer names, nearby text annotations) to classify elements as beams, slabs, or pillars.
Uses layer classification to filter noise (dimension lines, hatching, etc.).
"""

import math
from typing import List, Set, Dict, Optional
from src.pipeline.stage_segment import LevelSegment
from src.pipeline.stage_parse import TextEntity
from src.parser.segment_classifier import (
    find_beam_candidates, find_centerline_beam_candidates, find_pillar_candidates,
)
from src.parser.text_classifier import classify_text, extract_section, TextClassification
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.confidence import calculate_confidence

# Maximum perpendicular distance from beam axis to associate text (m)
MAX_TEXT_PERP_DIST = 3.0  # text within 3m perpendicular to beam axis

# Maximum distance to associate text with a point element (pillar center)
MAX_TEXT_DISTANCE = 3.0  # in meters (real coordinates)

# Minimum historical confidence to accept a layer from learning data
MIN_LEARNED_LAYER_CONFIDENCE = 0.80

# Minimum detection rate for a learned layer to be accepted in the current DXF
# Prevents accepting rebar/detailing layers that accidentally have a few parallel pairs
MIN_LEARNED_LAYER_RATE = 0.10


def _find_nearest_texts(
    x: float, y: float, texts: List[TextEntity], max_dist: float = MAX_TEXT_DISTANCE,
) -> List[TextEntity]:
    nearby = []
    for t in texts:
        dist = math.hypot(t.x - x, t.y - y)
        if dist <= max_dist:
            nearby.append(t)
    return nearby


def _find_texts_along_beam(
    p1: tuple, p2: tuple, texts: List[TextEntity],
    scale: float, max_perp_dist: float = MAX_TEXT_PERP_DIST,
) -> List[TextEntity]:
    """Find texts near the entire beam axis, not just the midpoint.

    Uses perpendicular distance to the beam line segment, with a small
    extension beyond the endpoints to catch labels placed at beam ends.
    """
    # Beam coords are in real meters, text coords in DXF units
    ax, ay = p1[0] / scale, p1[1] / scale
    bx, by = p2[0] / scale, p2[1] / scale
    max_perp_dxf = max_perp_dist / scale
    # Extend beam segment by 2m at each end to catch end-of-beam labels
    ext = 2.0 / scale
    dx, dy = bx - ax, by - ay
    seg_len = math.hypot(dx, dy)
    if seg_len < 0.01:
        return _find_nearest_texts((ax + bx) / 2, (ay + by) / 2, texts, max_perp_dist / scale)

    ux, uy = dx / seg_len, dy / seg_len
    # Extended endpoints
    eax, eay = ax - ux * ext, ay - uy * ext
    ebx, eby = bx + ux * ext, by + uy * ext
    edx, edy = ebx - eax, eby - eay
    elen_sq = edx * edx + edy * edy

    nearby = []
    for t in texts:
        # Project text onto extended beam line
        tp = ((t.x - eax) * edx + (t.y - eay) * edy) / elen_sq
        tp = max(0.0, min(1.0, tp))
        proj_x = eax + tp * edx
        proj_y = eay + tp * edy
        perp_dist = math.hypot(t.x - proj_x, t.y - proj_y)
        if perp_dist <= max_perp_dxf:
            nearby.append(t)
    return nearby


def _is_nervura_layer(pillars, max_count: int = 60) -> bool:
    """Detect if pillar candidates are actually nervura/waffle slab ribs.

    Nervura ribs are densely packed and/or highly uniform in size.
    Real pillars are spaced 3-8m apart with varied dimensions.
    Returns True if the candidates look like nervura rather than real pillars.

    Detection criteria (any triggers rejection):
    1. Tight packing: NN distance < 1.5m for >50% of candidates
    2. Uniform size: dominant rect size covers >60% of candidates
    """
    if len(pillars) <= max_count:
        return False

    import math as _math
    from collections import Counter

    # Check 1: Size uniformity — nervura ribs are all the same size
    sizes = Counter(
        (round(p.width_m, 2), round(p.depth_m, 2)) for p in pillars
    )
    dominant_count = sizes.most_common(1)[0][1] if sizes else 0
    if dominant_count / len(pillars) > 0.60:
        return True  # >60% same size = nervura, not pillars

    # Check 2: Tight packing (NN distance < 1.5m for most)
    # Sample up to 100 for performance
    positions = [(p.cx, p.cy) for p in pillars]
    sample = positions[:100]
    tight_count = 0
    for i, (x1, y1) in enumerate(sample):
        min_dist = 999.0
        for j, (x2, y2) in enumerate(positions):
            if i == j:
                continue
            d = _math.hypot(x1 - x2, y1 - y2)
            if d < min_dist:
                min_dist = d
        if min_dist < 1.50:
            tight_count += 1
    return tight_count / len(sample) > 0.50


def _classify_layers(
    level: LevelSegment,
    known_beam_layers: Optional[Dict[str, float]] = None,
    known_pillar_layers: Optional[Dict[str, float]] = None,
    scale: float = 1.0,
) -> Dict[str, ElementType]:
    """Classify layers by running structural detection per-layer.

    Strategy: run beam/pillar detection independently on each layer's entities.
    The layer that produces the most valid structural candidates (with best scores)
    is the structural layer for that type. This directly tests geometric quality
    rather than relying on text proximity which can be misleading.

    When learning data is available, layers with high historical confidence
    are also accepted if they contain valid structural candidates in this DXF.

    Returns a map of layer_name -> ElementType for structural layers.
    """
    from collections import Counter, defaultdict

    known_beam_layers = known_beam_layers or {}
    known_pillar_layers = known_pillar_layers or {}

    # Group segments by layer (apply scale so geometric thresholds work in meters)
    segs_by_layer: Dict[str, list] = defaultdict(list)
    for s in level.segments:
        if s.type == "H":
            segs_by_layer[s.layer].append({
                "type": "H", "y": s.y * scale,
                "x_min": s.x_min * scale, "x_max": s.x_max * scale,
            })
        else:
            segs_by_layer[s.layer].append({
                "type": "V", "x": s.x * scale,
                "y_min": s.y_min * scale, "y_max": s.y_max * scale,
            })

    # Group rects by layer (apply scale)
    rects_by_layer: Dict[str, list] = defaultdict(list)
    for r in level.rects:
        rects_by_layer[r.layer].append({
            "cx": r.cx * scale, "cy": r.cy * scale,
            "width": r.width * scale, "height": r.height * scale,
            "area": r.area * scale * scale,
        })

    # A layer can be BOTH beam and pillar (e.g., layer "1" contains
    # the main structural grid with both beam outlines and pillar fills).
    # We track beam and pillar layers independently, then merge.
    beam_layers: set = set()
    pillar_layers: set = set()

    # Multi-layer beam selection: accept ALL layers that qualify.
    MIN_BEAM_COUNT = 3
    MIN_BEAM_LAYER_RATE = 0.03  # 3% of segments must be beams
    for layer, seg_dicts in segs_by_layer.items():
        beams = find_beam_candidates(seg_dicts)
        if not beams or len(beams) < MIN_BEAM_COUNT:
            continue
        rate = len(beams) / max(len(seg_dicts), 1)
        if rate >= MIN_BEAM_LAYER_RATE:
            beam_layers.add(layer)

    # Fallback: if no layer has MIN_BEAM_COUNT, pick the one with best rate
    if not beam_layers:
        best_rate = 0
        best_beam_layer = None
        for layer, seg_dicts in segs_by_layer.items():
            beams = find_beam_candidates(seg_dicts)
            if not beams:
                continue
            rate = len(beams) / max(len(seg_dicts), 1)
            if rate > best_rate:
                best_rate = rate
                best_beam_layer = layer
        if best_beam_layer:
            beam_layers.add(best_beam_layer)

    # Accept additional beam layers from learning history
    for layer, confidence in known_beam_layers.items():
        if layer in beam_layers:
            continue
        if confidence < MIN_LEARNED_LAYER_CONFIDENCE:
            continue
        if layer not in segs_by_layer:
            continue
        beams = find_beam_candidates(segs_by_layer[layer])
        if beams:
            rate = len(beams) / max(len(segs_by_layer[layer]), 1)
            if rate >= MIN_LEARNED_LAYER_RATE:
                beam_layers.add(layer)

    # Pillar layers: accept ALL layers that contain valid pillar candidates.
    MAX_REALISTIC_PILLARS = 60
    MIN_PILLAR_RATE = 0.05
    MIN_PILLAR_COUNT = 2
    for layer, rect_dicts in rects_by_layer.items():
        pillars = find_pillar_candidates(rect_dicts)
        if not pillars or len(pillars) < MIN_PILLAR_COUNT:
            continue
        if _is_nervura_layer(pillars, MAX_REALISTIC_PILLARS):
            continue
        rate = len(pillars) / max(len(rect_dicts), 1)
        if rate >= MIN_PILLAR_RATE:
            pillar_layers.add(layer)

    # Accept additional pillar layers from learning history
    for layer, confidence in known_pillar_layers.items():
        if layer in pillar_layers:
            continue
        if confidence < MIN_LEARNED_LAYER_CONFIDENCE:
            continue
        if layer not in rects_by_layer:
            continue
        pillars = find_pillar_candidates(rects_by_layer[layer])
        if pillars:
            if _is_nervura_layer(pillars, MAX_REALISTIC_PILLARS):
                continue
            rate = len(pillars) / max(len(rects_by_layer[layer]), 1)
            if rate >= MIN_LEARNED_LAYER_RATE:
                pillar_layers.add(layer)

    # Merge: beam layers take priority in the result dict (since classify_elements
    # uses result to filter segments for beam detection). Pillar detection runs
    # on rects independently and doesn't need layer filtering.
    result = {}
    for layer in pillar_layers:
        result[layer] = ElementType.PILLAR
    for layer in beam_layers:
        result[layer] = ElementType.BEAM  # Overwrite pillar if dual-purpose

    return result


def classify_elements(
    level: LevelSegment,
    scale: float = 1.0,
    known_beam_layers: Optional[Dict[str, float]] = None,
    known_pillar_layers: Optional[Dict[str, float]] = None,
) -> List[ClassifiedElement]:
    elements: List[ClassifiedElement] = []

    # Classify layers to filter noise (with learning boost)
    layer_types = _classify_layers(
        level,
        known_beam_layers=known_beam_layers,
        known_pillar_layers=known_pillar_layers,
        scale=scale,
    )
    beam_layers = {l for l, t in layer_types.items() if t == ElementType.BEAM}
    pillar_layers = {l for l, t in layer_types.items() if t == ElementType.PILLAR}
    # Layers classified as BEAM can also contain pillar rects (shared structural layers).
    # Include beam layers in pillar search so their rects are not filtered out.
    pillar_layers = pillar_layers | beam_layers

    # Strict layer filter: when beam layers are identified, ONLY use those layers
    # This eliminates dimension lines, hatching, and other noise from unclassified layers
    seg_dicts = []
    for s in level.segments:
        if beam_layers and s.layer not in beam_layers:
            continue  # Only use segments from beam-classified layers
        if s.type == "H":
            seg_dicts.append({"type": "H", "y": s.y * scale, "x_min": s.x_min * scale, "x_max": s.x_max * scale})
        else:
            seg_dicts.append({"type": "V", "x": s.x * scale, "y_min": s.y_min * scale, "y_max": s.y_max * scale})

    # Beams from geometry (parallel pairs + centerlines)
    beam_candidates = find_beam_candidates(seg_dicts)

    # Centerline beam detection disabled — produces too many false positives
    # (dimension lines, grid lines, detail lines misidentified as beams).
    # Parallel-pair detection is the reliable primary method.

    for bc in beam_candidates:
        if bc.direction == "x":
            beam_geometry = [(bc.start, bc.axis_coord), (bc.end, bc.axis_coord)]
        else:
            beam_geometry = [(bc.axis_coord, bc.start), (bc.axis_coord, bc.end)]

        # Find text along the entire beam axis (not just midpoint)
        nearby = _find_texts_along_beam(
            beam_geometry[0], beam_geometry[1], level.texts, scale,
        )
        text_cls = TextClassification(ElementType.UNKNOWN, None, 0.0)
        section = None
        for t in nearby:
            tc = classify_text(t.content)
            # For beams: only consider beam-confirming or slab-indicating text.
            # Pillar labels (P1, P20) are commonly near beams (beams connect to pillars)
            # and should NOT override beam detection.
            if tc.element_type != ElementType.PILLAR and tc.score > text_cls.score:
                text_cls = tc
            s = extract_section(t.content)
            if s:
                section = s

        # Text override: only skip if text clearly says SLAB (not pillar — pillars are expected near beams)
        if text_cls.element_type == ElementType.SLAB and text_cls.score >= 0.80:
            continue

        agree = text_cls.element_type in (ElementType.BEAM, ElementType.UNKNOWN)
        score_final = calculate_confidence(bc.score, text_cls.score, agree)

        # For beams, width is always the smaller dimension, height the larger
        if section:
            sec_w = min(section[0], section[1])
            sec_h = max(section[0], section[1])
        else:
            sec_w = bc.width_m
            sec_h = None

        # Fallback name: position-based identifier for unnamed beams
        beam_name = text_cls.name
        if not beam_name:
            if bc.direction == "x":
                beam_name = f"Eixo Y={bc.axis_coord:.1f} ({bc.start:.1f}-{bc.end:.1f})"
            else:
                beam_name = f"Eixo X={bc.axis_coord:.1f} ({bc.start:.1f}-{bc.end:.1f})"

        el = ClassifiedElement(
            element_type=ElementType.BEAM,
            geometry=beam_geometry,
            score_geometric=bc.score,
            score_textual=text_cls.score,
            score_final=score_final,
            name=beam_name,
            section_width_m=sec_w,
            section_height_m=sec_h,
            length_m=bc.length_m,
            source_layer="",
        )
        elements.append(el)

    # Strict layer filter: when pillar layers are identified, ONLY use those layers
    rect_dicts = []
    for r in level.rects:
        if pillar_layers and r.layer not in pillar_layers:
            continue
        rect_dicts.append({
            "cx": r.cx * scale, "cy": r.cy * scale,
            "width": r.width * scale, "height": r.height * scale,
            "area": r.area * scale * scale,
        })

    pillar_candidates = find_pillar_candidates(rect_dicts)
    for pc in pillar_candidates:
        cx_dxf = pc.cx / scale
        cy_dxf = pc.cy / scale
        nearby = _find_nearest_texts(cx_dxf, cy_dxf, level.texts)
        # For pillars, only consider pillar-confirming text. Beam and slab labels
        # are commonly near pillars (beams connect to pillars, slabs span between them)
        # and should not penalize pillar confidence.
        text_cls = TextClassification(ElementType.UNKNOWN, None, 0.0)
        for t in nearby:
            tc = classify_text(t.content)
            if tc.element_type == ElementType.PILLAR and tc.score > text_cls.score:
                text_cls = tc

        agree = text_cls.element_type in (ElementType.PILLAR, ElementType.UNKNOWN)
        score_final = calculate_confidence(pc.score, text_cls.score, agree)

        # Only attach the name if text agrees this is a pillar
        pillar_name = text_cls.name if agree else None

        el = ClassifiedElement(
            element_type=ElementType.PILLAR,
            geometry=[(pc.cx, pc.cy)],
            score_geometric=pc.score,
            score_textual=text_cls.score,
            score_final=score_final,
            name=pillar_name,
            section_width_m=pc.width_m,
            section_height_m=pc.depth_m,
            source_layer="",
        )
        elements.append(el)

    # Circular pillars from CIRCLE entities
    # Only detect if there's a significant cluster of same-radius circles
    # (scattered circles at varied radii are usually annotation symbols)
    MIN_PILLAR_RADIUS = 0.10  # m — minimum radius for structural column
    MAX_PILLAR_RADIUS = 0.60  # m — maximum radius for structural column
    MIN_CIRCLE_CLUSTER = 5  # minimum circles at same radius to be structural
    CIRCLE_CLUSTER_TOLERANCE = 0.10  # m — deduplicate overlapping circles

    # --- Filter out level marker circles (cota de nível) ---
    # These are annotation circles with a cross through the center and nearby
    # elevation text (+3,80 etc.). They are NOT structural pillars.
    import re as _re
    _ELEVATION_PATTERN = _re.compile(r"[+\-]\s*\d+[,\.]\d+")

    level_marker_positions: set = set()
    for c in level.circles:
        cx_s, cy_s = c.cx * scale, c.cy * scale
        r_s = c.radius * scale

        # Check for nearby elevation text (within 2× radius)
        has_elevation_text = False
        for t in level.texts:
            dist = math.hypot(c.cx - t.x, c.cy - t.y)
            if dist < max(2.0 / scale, c.radius * 6):
                if _ELEVATION_PATTERN.search(t.content):
                    has_elevation_text = True
                    break

        if not has_elevation_text:
            continue

        # Check for cross pattern: H and V segments passing through center
        cross_count = 0
        for seg in level.segments:
            if seg.type == "H":
                # H segment must pass through circle vertically
                if abs(seg.y - c.cy) < c.radius * 0.8:
                    if seg.x_min <= c.cx + c.radius * 0.5 and seg.x_max >= c.cx - c.radius * 0.5:
                        seg_len = seg.x_max - seg.x_min
                        if seg_len < c.radius * 4:  # short segment, not a beam
                            cross_count += 1
            elif seg.type == "V":
                if abs(seg.x - c.cx) < c.radius * 0.8:
                    if seg.y_min <= c.cy + c.radius * 0.5 and seg.y_max >= c.cy - c.radius * 0.5:
                        seg_len = seg.y_max - seg.y_min
                        if seg_len < c.radius * 4:
                            cross_count += 1

        # Require BOTH elevation text AND cross pattern to be confident
        # it's a level marker (just elevation text nearby could be coincidence)
        if cross_count >= 2 and has_elevation_text:
            level_marker_positions.add(
                (round(cx_s / CIRCLE_CLUSTER_TOLERANCE) * CIRCLE_CLUSTER_TOLERANCE,
                 round(cy_s / CIRCLE_CLUSTER_TOLERANCE) * CIRCLE_CLUSTER_TOLERANCE)
            )

    # Count circles by rounded radius to find structural patterns
    from collections import Counter
    radius_counts: Counter = Counter()
    for c in level.circles:
        r = c.radius * scale
        if MIN_PILLAR_RADIUS <= r <= MAX_PILLAR_RADIUS:
            radius_counts[round(r, 2)] += 1

    # Only process circles whose radius appears enough times
    structural_radii = {r for r, count in radius_counts.items() if count >= MIN_CIRCLE_CLUSTER}
    if structural_radii:
        seen_circles: set = set()
        for c in level.circles:
            r = c.radius * scale
            if r < MIN_PILLAR_RADIUS or r > MAX_PILLAR_RADIUS:
                continue
            if round(r, 2) not in structural_radii:
                continue
            key = (round(c.cx * scale / CIRCLE_CLUSTER_TOLERANCE) * CIRCLE_CLUSTER_TOLERANCE,
                   round(c.cy * scale / CIRCLE_CLUSTER_TOLERANCE) * CIRCLE_CLUSTER_TOLERANCE)
            if key in seen_circles:
                continue
            # Skip level marker circles (cota de nível)
            if key in level_marker_positions:
                continue
            seen_circles.add(key)

            diameter = r * 2
            geo_score = min(0.85, 0.60 + 0.10 * (1.0 - abs(r - 0.15) / 0.45))

            cx_dxf = c.cx
            cy_dxf = c.cy
            nearby = _find_nearest_texts(cx_dxf, cy_dxf, level.texts)
            text_cls = TextClassification(ElementType.UNKNOWN, None, 0.0)
            for t in nearby:
                tc = classify_text(t.content)
                if tc.element_type == ElementType.PILLAR and tc.score > text_cls.score:
                    text_cls = tc

            agree = text_cls.element_type in (ElementType.PILLAR, ElementType.UNKNOWN)
            score_final = calculate_confidence(geo_score, text_cls.score, agree)
            pillar_name = text_cls.name if agree else None

            el = ClassifiedElement(
                element_type=ElementType.PILLAR,
                geometry=[(c.cx * scale, c.cy * scale)],
                score_geometric=geo_score,
                score_textual=text_cls.score,
                score_final=score_final,
                name=pillar_name,
                section_width_m=diameter,
                section_height_m=diameter,
                source_layer=c.layer,
            )
            elements.append(el)

    # === TEXT-BASED PILLAR DETECTION ===
    # Many DXF files have pillar labels ("P1", "P15") with section text ("30x19")
    # but no SOLID/rect geometry at that location. Detect pillars from text when
    # no geometric pillar was found nearby.
    # This catches pillars that the geometric detector misses.
    TEXT_PILLAR_DEDUP_DIST = 1.50  # m — don't create text pillar if geometric one within this distance
    SECTION_SEARCH_RADIUS = 2.0   # m — max distance to find a section text near a pillar label

    import re as _re
    _pillar_label_re = _re.compile(r"^P(\d+)\w*$", _re.IGNORECASE)
    _section_re = _re.compile(r"(\d+)\s*[x/]\s*(\d+)")

    # Collect existing pillar positions for deduplication
    existing_pillar_pos = set()
    for el in elements:
        if el.element_type == ElementType.PILLAR and el.geometry:
            px, py = el.geometry[0]
            existing_pillar_pos.add((
                round(px / TEXT_PILLAR_DEDUP_DIST) * TEXT_PILLAR_DEDUP_DIST,
                round(py / TEXT_PILLAR_DEDUP_DIST) * TEXT_PILLAR_DEDUP_DIST,
            ))

    # Find pillar label texts
    pillar_texts = []
    for t in level.texts:
        m = _pillar_label_re.match(t.content.strip())
        if m:
            pillar_texts.append(t)

    for pt in pillar_texts:
        # Check if a geometric pillar already exists nearby
        dedup_key = (
            round(pt.x * scale / TEXT_PILLAR_DEDUP_DIST) * TEXT_PILLAR_DEDUP_DIST,
            round(pt.y * scale / TEXT_PILLAR_DEDUP_DIST) * TEXT_PILLAR_DEDUP_DIST,
        )
        if dedup_key in existing_pillar_pos:
            continue

        # Also check euclidean distance to any existing pillar
        too_close = False
        for el in elements:
            if el.element_type == ElementType.PILLAR and el.geometry:
                px, py = el.geometry[0]
                if math.hypot(pt.x * scale - px, pt.y * scale - py) < TEXT_PILLAR_DEDUP_DIST:
                    too_close = True
                    break
        if too_close:
            continue

        # Look for section text ("bxh") nearby
        sec_w, sec_h = None, None
        for t2 in level.texts:
            if t2 is pt:
                continue
            dist = math.hypot(t2.x - pt.x, t2.y - pt.y)
            if dist > SECTION_SEARCH_RADIUS / scale:
                continue
            sm = _section_re.match(t2.content.strip())
            if sm:
                # Section in cm -> convert to meters
                sec_w = int(sm.group(1)) / 100.0
                sec_h = int(sm.group(2)) / 100.0
                break

        # Default pillar section if no text found
        if sec_w is None:
            sec_w = 0.30
            sec_h = 0.30

        # Try to find the nearest SOLID/rect to use as the real pillar center.
        # Text labels are offset from the actual pillar position (typically
        # below or beside it). The SOLID fill IS the pillar outline.
        RECT_SEARCH_RADIUS = 2.0  # m — search for rect near text label
        pillar_cx = pt.x * scale
        pillar_cy = pt.y * scale
        best_rect_dist = RECT_SEARCH_RADIUS
        for r in level.rects:
            rx, ry = r.cx * scale, r.cy * scale
            rw, rh = r.width * scale, r.height * scale
            # Rect must be plausible pillar size
            if rw < 0.10 or rh < 0.10 or rw > 1.0 or rh > 1.0:
                continue
            d = math.hypot(rx - pillar_cx, ry - pillar_cy)
            if d < best_rect_dist:
                best_rect_dist = d
                pillar_cx = rx
                pillar_cy = ry
                # Use rect dimensions as section (more accurate than text)
                sec_w = max(sec_w, rw)
                sec_h = max(sec_h, rh)

        pillar_name = pt.content.strip()
        el = ClassifiedElement(
            element_type=ElementType.PILLAR,
            geometry=[(pillar_cx, pillar_cy)],
            score_geometric=0.30 if best_rect_dist < RECT_SEARCH_RADIUS else 0.0,
            score_textual=0.85,
            score_final=0.75,
            name=pillar_name,
            section_width_m=sec_w,
            section_height_m=sec_h,
            source_layer="text_detected",
        )
        elements.append(el)
        existing_pillar_pos.add(dedup_key)

    return elements
