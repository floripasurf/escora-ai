"""Stage 3: Combined geometric + textual classification.

Combines geometric signal (parallel pairs, small rects) with textual signal
(layer names, nearby text annotations) to classify elements as beams, slabs, or pillars.
"""

import math
from typing import List
from src.pipeline.stage_segment import LevelSegment
from src.pipeline.stage_parse import TextEntity
from src.parser.segment_classifier import find_beam_candidates, find_pillar_candidates
from src.parser.text_classifier import classify_text, extract_section, TextClassification
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.models.confidence import calculate_confidence

# Maximum distance to associate a text annotation with a geometric element
MAX_TEXT_DISTANCE = 2.0  # in DXF units (before scaling)


def _find_nearest_texts(
    x: float, y: float, texts: List[TextEntity], max_dist: float = MAX_TEXT_DISTANCE,
) -> List[TextEntity]:
    nearby = []
    for t in texts:
        dist = math.hypot(t.x - x, t.y - y)
        if dist <= max_dist:
            nearby.append(t)
    return nearby


def classify_elements(level: LevelSegment, scale: float = 1.0) -> List[ClassifiedElement]:
    elements: List[ClassifiedElement] = []

    # Convert segments to dicts for segment_classifier
    seg_dicts = []
    for s in level.segments:
        if s.type == "H":
            seg_dicts.append({"type": "H", "y": s.y * scale, "x_min": s.x_min * scale, "x_max": s.x_max * scale})
        else:
            seg_dicts.append({"type": "V", "x": s.x * scale, "y_min": s.y_min * scale, "y_max": s.y_max * scale})

    # Beams from geometry
    beam_candidates = find_beam_candidates(seg_dicts, min_length=0.5)
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
            if tc.score > text_cls.score:
                text_cls = tc
            s = extract_section(t.content)
            if s:
                section = s

        agree = text_cls.element_type in (ElementType.BEAM, ElementType.UNKNOWN)
        score_final = calculate_confidence(bc.score, text_cls.score, agree)

        el = ClassifiedElement(
            element_type=ElementType.BEAM,
            geometry=[],  # simplified for now
            score_geometric=bc.score,
            score_textual=text_cls.score,
            score_final=score_final,
            name=text_cls.name,
            section_width_m=section[0] if section else bc.width_m,
            section_height_m=section[1] if section else None,
            length_m=bc.length_m,
            source_layer="",
        )
        elements.append(el)

    # Pillars from rectangles
    rect_dicts = [
        {"cx": r.cx * scale, "cy": r.cy * scale,
         "width": r.width * scale, "height": r.height * scale,
         "area": r.area * scale * scale}
        for r in level.rects
    ]
    pillar_candidates = find_pillar_candidates(rect_dicts)
    for pc in pillar_candidates:
        cx_dxf = pc.cx / scale
        cy_dxf = pc.cy / scale
        nearby = _find_nearest_texts(cx_dxf, cy_dxf, level.texts)
        text_cls = TextClassification(ElementType.UNKNOWN, None, 0.0)
        for t in nearby:
            tc = classify_text(t.content)
            if tc.score > text_cls.score:
                text_cls = tc

        agree = text_cls.element_type in (ElementType.PILLAR, ElementType.UNKNOWN)
        score_final = calculate_confidence(pc.score, text_cls.score, agree)

        el = ClassifiedElement(
            element_type=ElementType.PILLAR,
            geometry=[],
            score_geometric=pc.score,
            score_textual=text_cls.score,
            score_final=score_final,
            name=text_cls.name,
            section_width_m=pc.width_m,
            section_height_m=pc.depth_m,
            source_layer="",
        )
        elements.append(el)

    return elements
