"""Pipeline runner: orchestrates Stages 1-7 sequentially.

Stage 0: Load learning store
Stage 1: Parse DXF (entities, texts, hatches, dimensions, INSERT blocks)
Stage 1.5: Region filter (remove detail views, sections, title blocks)
Stage 1.6: Classify construction type and slab type
Stage 2: Segment by level
Stage 3+4: Classify elements + metadata
Stage 5: Calculation
Stage 6: Learning
"""

import logging
from typing import List, Optional
from src.pipeline.stage_parse import parse_dxf
from src.pipeline.stage_segment import segment_by_level
from src.pipeline.stage_classify import classify_elements
from src.pipeline.stage_metadata import extract_pe_direito, extract_level_height, extract_slab_thickness
from src.pipeline.stage_calculate import run_calculation
from src.pipeline.stage_learn import learn_and_save
from src.pipeline.learning_store import LearningStore
from src.parser.region_filter import filter_main_plan
from src.parser.construction_classifier import classify_construction, ConstructionType
from src.models.pipeline_models import LevelGroup, PipelineResult
from src.utils.constants import ALTURA_DEFAULT

logger = logging.getLogger(__name__)


DEFAULT_SCALE = 0.02  # 1:50 fallback
REAL_COORDS_THRESHOLD = 5.0  # If bounding box > 5 units, assume real-world meters


def _detect_coordinate_scale(parse) -> float:
    """Auto-detect if DXF coordinates are in real meters or drawing units.

    Most modern CAD files use model space in real-world meters.
    The 'ESC 1:50' text is a print/layout scale, not coordinate scale.
    If the coordinate range exceeds REAL_COORDS_THRESHOLD, assume real meters.
    """
    all_y = [s.y for s in parse.segments if s.type == "H"]
    all_x = [s.x for s in parse.segments if s.type == "V"]
    all_y.extend(s.y_min for s in parse.segments if s.type == "V")
    all_y.extend(s.y_max for s in parse.segments if s.type == "V")
    all_x.extend(s.x_min for s in parse.segments if s.type == "H")
    all_x.extend(s.x_max for s in parse.segments if s.type == "H")

    if not all_x or not all_y:
        return parse.detected_scale or DEFAULT_SCALE

    x_range = max(all_x) - min(all_x)
    y_range = max(all_y) - min(all_y)

    if max(x_range, y_range) > REAL_COORDS_THRESHOLD:
        return 1.0  # Coordinates are already in meters

    return parse.detected_scale or DEFAULT_SCALE


def run_pipeline(filepath: str, scale_override: Optional[float] = None) -> PipelineResult:
    # Stage 0: Load learning store for accumulated knowledge
    store = LearningStore()
    known_beam_layers = store.get_known_beam_layers() if store.run_count > 0 else {}
    known_pillar_layers = store.get_known_pillar_layers() if store.run_count > 0 else {}
    learned_section_height = store.get_default_section_height() if store.run_count > 0 else None
    learned_pe_direito = store.get_pe_direito_history() if store.run_count > 0 else None

    if store.run_count > 0:
        logger.info(
            f"Learning data loaded: {store.run_count} runs, "
            f"{len(known_beam_layers)} beam layers, "
            f"{len(known_pillar_layers)} pillar layers"
        )

    # Stage 1: Parse
    parse = parse_dxf(filepath)

    scale = scale_override or _detect_coordinate_scale(parse)

    # Stage 1.5: Region filter — remove detail views, sections, title blocks
    (
        parse.texts, parse.segments, parse.rects,
        parse.circles, parse.polylines, parse.hatches,
        parse.dimensions, region_warnings,
    ) = filter_main_plan(
        parse.texts, parse.segments, parse.rects,
        parse.circles, parse.polylines, parse.hatches,
        parse.dimensions,
    )

    # Stage 1.6: Classify construction type and slab type
    classification = classify_construction(
        texts=parse.texts,
        layers=parse.layers,
        segments=parse.segments,
        rects=parse.rects,
        hatches=parse.hatches,
        dimensions=parse.dimensions,
        polylines=parse.polylines,
    )
    logger.info(
        f"Construction: {classification.construction_type.value} "
        f"({classification.construction_confidence:.0%}), "
        f"Slab: {classification.slab_type.value} "
        f"({classification.slab_confidence:.0%})"
    )

    # Stage 2: Segment by level
    level_segments = segment_by_level(parse)

    # Stage 3 + 4: Classify + metadata for each level
    levels: List[LevelGroup] = []
    warnings: List[str] = []
    all_elements = []

    # Add classification info and region filter warnings
    warnings.append(
        f"Tipo de obra: {classification.construction_type.value} "
        f"({classification.construction_confidence:.0%})"
    )
    if classification.slab_type.value != "unknown":
        warnings.append(
            f"Tipo de laje: {classification.slab_type.value} "
            f"({classification.slab_confidence:.0%})"
        )
    warnings.extend(classification.signals)
    warnings.extend(region_warnings)

    for seg in level_segments:
        elements = classify_elements(
            seg, scale=scale,
            known_beam_layers=known_beam_layers,
            known_pillar_layers=known_pillar_layers,
        )

        pe_direito = extract_pe_direito(seg.texts)
        level_height = extract_level_height(seg.texts)

        pe_direito_is_default = pe_direito is None
        if pe_direito_is_default:
            if learned_pe_direito:
                pe_direito = learned_pe_direito
                warnings.append(
                    f"Pe-direito nao encontrado no nivel {seg.level_name} — "
                    f"usando {learned_pe_direito:.2f}m aprendido de execuções anteriores"
                )
            else:
                warnings.append(f"Pe-direito nao encontrado no nivel {seg.level_name}")
                pe_direito = ALTURA_DEFAULT

        level = LevelGroup(
            level_name=seg.level_name,
            level_height_m=level_height,
            pe_direito_m=pe_direito,
            elements=elements,
        )
        levels.append(level)
        all_elements.extend(elements)

    # Stage 5: Calculation
    calculation = None
    if all_elements:
        pe_direito = levels[0].pe_direito_m or ALTURA_DEFAULT
        pe_direito_is_default = levels[0].pe_direito_m is None

        slab_thickness = None
        for seg in level_segments:
            slab_thickness = extract_slab_thickness(seg.texts)
            if slab_thickness is not None:
                break

        # Collect all rects for nervura detection
        all_rects = []
        for seg in level_segments:
            for r in seg.rects:
                all_rects.append({
                    "cx": r.cx, "cy": r.cy,
                    "width": r.width, "height": r.height,
                    "area": r.area, "layer": r.layer,
                })

        # Collect segments from beam layers for slab derivation fallback.
        # When classified beams are too sparse for polygonize, we use ALL
        # beam candidates from the beam layer (not just the ones that pass
        # text-based classification) to derive slab panels.
        all_beam_layer_segs = []
        for seg in level_segments:
            # Get beam layers for this level (same logic as stage_classify)
            from src.pipeline.stage_classify import _classify_layers
            from src.models.pipeline_models import ElementType as _ET
            layer_types = _classify_layers(seg)
            beam_layers = {l for l, t in layer_types.items() if t == _ET.BEAM}
            if not beam_layers:
                continue
            for s in seg.segments:
                if s.layer not in beam_layers:
                    continue
                if s.type == "H":
                    all_beam_layer_segs.append({
                        "type": "H", "y": s.y * scale,
                        "x_min": s.x_min * scale, "x_max": s.x_max * scale,
                    })
                else:
                    all_beam_layer_segs.append({
                        "type": "V", "x": s.x * scale,
                        "y_min": s.y_min * scale, "y_max": s.y_max * scale,
                    })

        # Collect hatches and closed polylines for direct slab boundary detection
        all_hatches = []
        all_polylines = []
        for seg in level_segments:
            for h in seg.hatches:
                all_hatches.append({
                    "points": h.points,
                    "layer": h.layer,
                    "pattern_name": h.pattern_name,
                    "is_solid": h.is_solid,
                    "area": h.area,
                })
            for pl in seg.polylines:
                all_polylines.append({
                    "points": pl.points,
                    "layer": pl.layer,
                    "is_closed": pl.is_closed,
                })

        try:
            calculation = run_calculation(
                elements=all_elements,
                pe_direito_m=pe_direito,
                pe_direito_is_default=pe_direito_is_default,
                slab_thickness_m=slab_thickness,
                learned_section_height_m=learned_section_height,
                slab_type=classification.slab_type.value,
                nervura_rects=all_rects,
                beam_layer_segments=all_beam_layer_segs,
                slab_hatches=all_hatches,
                slab_polylines=all_polylines,
            )
            warnings.extend(calculation.warnings)
        except Exception as e:
            warnings.append(f"Cálculo falhou: {e}")

    result = PipelineResult(
        filename=parse.filename,
        scale=scale,
        construction_type=classification.construction_type.value,
        slab_type=classification.slab_type.value,
        levels=levels,
        warnings=warnings,
        calculation=calculation,
    )

    # Stage 6: Learning — save what we learned from this run
    try:
        learn_and_save(result, level_segments=level_segments, store=store)
    except Exception as e:
        logger.warning(f"Learning stage failed (non-fatal): {e}")

    return result
