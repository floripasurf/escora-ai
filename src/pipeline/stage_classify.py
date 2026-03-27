"""Stage 3: Combined geometric + textual classification.

Combines geometric signal (parallel pairs, small rects) with textual signal
(layer names, nearby text annotations) to classify elements as beams, slabs, or pillars.
Uses layer classification to filter noise (dimension lines, hatching, etc.).
"""

import math
from typing import List, Set, Dict, Optional
from src.pipeline.stage_segment import LevelSegment
from src.pipeline.stage_parse import TextEntity
from src.parser.segment_classifier import find_beam_candidates, find_pillar_candidates
from src.parser.text_classifier import classify_text, extract_section, TextClassification
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.confidence import calculate_confidence

# Maximum distance to associate a text annotation with a geometric element
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


def _classify_layers(
    level: LevelSegment,
    known_beam_layers: Optional[Dict[str, float]] = None,
    known_pillar_layers: Optional[Dict[str, float]] = None,
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

    # Group segments by layer
    segs_by_layer: Dict[str, list] = defaultdict(list)
    for s in level.segments:
        if s.type == "H":
            segs_by_layer[s.layer].append({"type": "H", "y": s.y, "x_min": s.x_min, "x_max": s.x_max})
        else:
            segs_by_layer[s.layer].append({"type": "V", "x": s.x, "y_min": s.y_min, "y_max": s.y_max})

    # Group rects by layer
    rects_by_layer: Dict[str, list] = defaultdict(list)
    for r in level.rects:
        rects_by_layer[r.layer].append({
            "cx": r.cx, "cy": r.cy, "width": r.width, "height": r.height, "area": r.area,
        })

    result = {}

    # Best beam layer: uses a combined score of detection rate AND absolute count.
    # Pure rate favors tiny layers with 1 accidental beam (e.g., 1/13 = 7.7%).
    # Pure count favors huge noisy layers. Combined score balances both:
    #   score = beam_count * rate  (rewards layers with many beams at decent rate)
    # Minimum 3 beams to avoid fluky single-pair detections.
    MIN_BEAM_COUNT = 3
    best_beam_layer = None
    best_beam_score = 0
    for layer, seg_dicts in segs_by_layer.items():
        beams = find_beam_candidates(seg_dicts)
        if not beams or len(beams) < MIN_BEAM_COUNT:
            continue
        rate = len(beams) / max(len(seg_dicts), 1)
        score = len(beams) * rate
        if score > best_beam_score:
            best_beam_score = score
            best_beam_layer = layer
    if best_beam_layer:
        result[best_beam_layer] = ElementType.BEAM

    # Fallback: if no layer has MIN_BEAM_COUNT, pick the one with best rate
    if not best_beam_layer:
        best_rate = 0
        for layer, seg_dicts in segs_by_layer.items():
            beams = find_beam_candidates(seg_dicts)
            if not beams:
                continue
            rate = len(beams) / max(len(seg_dicts), 1)
            if rate > best_rate:
                best_rate = rate
                best_beam_layer = layer
        if best_beam_layer:
            result[best_beam_layer] = ElementType.BEAM

    # Accept additional beam layers from learning history
    # Only if they have candidates in this DXF, high historical confidence,
    # AND a reasonable detection rate (filters rebar/detailing noise)
    for layer, confidence in known_beam_layers.items():
        if layer in result:
            continue  # Already selected
        if confidence < MIN_LEARNED_LAYER_CONFIDENCE:
            continue
        if layer not in segs_by_layer:
            continue
        beams = find_beam_candidates(segs_by_layer[layer])
        if beams:
            rate = len(beams) / max(len(segs_by_layer[layer]), 1)
            if rate >= MIN_LEARNED_LAYER_RATE:
                result[layer] = ElementType.BEAM

    # Best pillar layer: highest detection rate (rect pillars found / total rects)
    best_pillar_layer = None
    best_pillar_rate = 0
    for layer, rect_dicts in rects_by_layer.items():
        pillars = find_pillar_candidates(rect_dicts)
        if not pillars:
            continue
        rate = len(pillars) / max(len(rect_dicts), 1)
        if rate > best_pillar_rate:
            best_pillar_rate = rate
            best_pillar_layer = layer
    if best_pillar_layer:
        result[best_pillar_layer] = ElementType.PILLAR

    # Accept additional pillar layers from learning history
    for layer, confidence in known_pillar_layers.items():
        if layer in result:
            continue
        if confidence < MIN_LEARNED_LAYER_CONFIDENCE:
            continue
        if layer not in rects_by_layer:
            continue
        pillars = find_pillar_candidates(rects_by_layer[layer])
        if pillars:
            rate = len(pillars) / max(len(rects_by_layer[layer]), 1)
            if rate >= MIN_LEARNED_LAYER_RATE:
                result[layer] = ElementType.PILLAR

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
    )
    beam_layers = {l for l, t in layer_types.items() if t == ElementType.BEAM}
    pillar_layers = {l for l, t in layer_types.items() if t == ElementType.PILLAR}

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

    # Beams from geometry
    beam_candidates = find_beam_candidates(seg_dicts)
    for bc in beam_candidates:
        # Find nearby text
        if bc.direction == "x":
            cx = (bc.start + bc.end) / 2 / scale
            cy = bc.axis_coord / scale
        else:
            cx = bc.axis_coord / scale
            cy = (bc.start + bc.end) / 2 / scale

        nearby = _find_nearest_texts(cx, cy, level.texts)
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

        if bc.direction == "x":
            beam_geometry = [(bc.start, bc.axis_coord), (bc.end, bc.axis_coord)]
        else:
            beam_geometry = [(bc.axis_coord, bc.start), (bc.axis_coord, bc.end)]

        # For beams, width is always the smaller dimension, height the larger
        if section:
            sec_w = min(section[0], section[1])
            sec_h = max(section[0], section[1])
        else:
            sec_w = bc.width_m
            sec_h = None

        el = ClassifiedElement(
            element_type=ElementType.BEAM,
            geometry=beam_geometry,
            score_geometric=bc.score,
            score_textual=text_cls.score,
            score_final=score_final,
            name=text_cls.name,
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

    # Count circles by rounded radius to find structural patterns
    from collections import Counter
    radius_counts: Counter = Counter()
    for c in level.circles:
        r = c.radius * scale
        if MIN_PILLAR_RADIUS <= r <= MAX_PILLAR_RADIUS:
            radius_counts[round(r, 2)] += 1

    # Only process circles whose radius appears enough times
    structural_radii = {r for r, count in radius_counts.items() if count >= MIN_CIRCLE_CLUSTER}
    if not structural_radii:
        return elements

    seen_circles: set = set()
    for c in level.circles:
        r = c.radius * scale
        if r < MIN_PILLAR_RADIUS or r > MAX_PILLAR_RADIUS:
            continue
        if round(r, 2) not in structural_radii:
            continue
        # Deduplicate by center position
        key = (round(c.cx * scale / CIRCLE_CLUSTER_TOLERANCE) * CIRCLE_CLUSTER_TOLERANCE,
               round(c.cy * scale / CIRCLE_CLUSTER_TOLERANCE) * CIRCLE_CLUSTER_TOLERANCE)
        if key in seen_circles:
            continue
        seen_circles.add(key)

        diameter = r * 2
        geo_score = min(0.85, 0.60 + 0.10 * (1.0 - abs(r - 0.15) / 0.45))

        cx_dxf = c.cx
        cy_dxf = c.cy
        nearby = _find_nearest_texts(cx_dxf, cy_dxf, level.texts)
        # Same as rect pillars: only consider pillar-confirming text
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

    return elements
