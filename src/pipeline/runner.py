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
from src.parser.structural_system import detect_structural_system, SystemRouting
from src.models.pipeline_models import LevelGroup, PipelineResult
from src.utils.constants import ALTURA_DEFAULT

logger = logging.getLogger(__name__)


DEFAULT_SCALE = 0.02  # 1:50 fallback

# $INSUNITS value → meters multiplier
_INSUNITS_TO_METERS = {
    1: 0.0254,   # inches
    2: 0.3048,   # feet
    4: 0.001,    # millimeters
    5: 0.01,     # centimeters
    6: 1.0,      # meters
}


def _detect_coordinate_scale(parse) -> float:
    """Auto-detect coordinate-to-meters multiplier using three methods.

    Priority:
    1. $INSUNITS DXF header (authoritative if present)
    2. Dimension entity calibration (compare measurement vs coordinate distance)
    3. Coordinate range heuristic (improved to handle cm-scale files)

    Returns a float multiplier: coordinates * scale = meters.
    """
    import math

    # --- Method 1: $INSUNITS header ---
    if parse.insunits is not None and parse.insunits in _INSUNITS_TO_METERS:
        scale = _INSUNITS_TO_METERS[parse.insunits]
        logger.info(
            f"Scale detection: $INSUNITS={parse.insunits} → scale={scale} "
            f"(method: DXF header)"
        )
        return scale

    # Collect coordinate ranges (needed for methods 2 and 3)
    all_y = [s.y for s in parse.segments if s.type == "H"]
    all_x = [s.x for s in parse.segments if s.type == "V"]
    all_y.extend(s.y_min for s in parse.segments if s.type == "V")
    all_y.extend(s.y_max for s in parse.segments if s.type == "V")
    all_x.extend(s.x_min for s in parse.segments if s.type == "H")
    all_x.extend(s.x_max for s in parse.segments if s.type == "H")

    if not all_x or not all_y:
        logger.info("Scale detection: no segments found, using text scale or default")
        return parse.detected_scale or DEFAULT_SCALE

    x_range = max(all_x) - min(all_x)
    y_range = max(all_y) - min(all_y)
    coord_range = max(x_range, y_range)

    # --- Method 2: Dimension entity calibration ---
    if parse.dimensions:
        ratios = []
        for dim in parse.dimensions:
            if dim.measurement <= 0 or dim.defpoint is None or dim.defpoint2 is None:
                continue
            dx = dim.defpoint[0] - dim.defpoint2[0]
            dy = dim.defpoint[1] - dim.defpoint2[1]
            coord_dist = math.hypot(dx, dy)
            if coord_dist < 1e-6:
                continue
            ratio = dim.measurement / coord_dist
            ratios.append(ratio)

        if len(ratios) >= 2:
            # Use median for robustness against outliers
            ratios.sort()
            median_ratio = ratios[len(ratios) // 2]
            # The ratio tells us: measurement_in_drawing_units / coord_distance
            # If ratio ≈ 1.0 → coords match measurements (both same unit)
            # If ratio ≈ 0.01 → measurements are 100x smaller (coords in cm, measurements in m)
            # We need to figure out what unit the measurement is in.
            # In construction DXFs, dimension measurements are typically in the
            # drawing's native unit. So the ratio itself IS the scale if measurements
            # represent meters, or we use it to detect unit mismatch.
            #
            # Common cases:
            #   coords=cm, measurement=cm → ratio ≈ 1.0, but coords are cm → scale=0.01
            #   coords=m, measurement=m → ratio ≈ 1.0, coords are m → scale=1.0
            #   coords=mm, measurement=mm → ratio ≈ 1.0, coords are mm → scale=0.001
            # The ratio alone can't distinguish, so we combine with coord_range.
            #
            # If ratio ≈ 1.0, fall through to heuristic (method 3) with high confidence.
            # If ratio ≈ 0.01, coords are likely 100x the measurement unit.
            # If ratio ≈ 0.001, coords are likely 1000x the measurement unit.
            if 0.005 < median_ratio < 0.05:
                # measurement ≈ coord / 100 → coords are cm, measurements are m
                logger.info(
                    f"Scale detection: dimension calibration ratio={median_ratio:.4f} "
                    f"({len(ratios)} dims) → scale=0.01 (method: dimension calibration, "
                    f"coords in cm)"
                )
                return 0.01
            elif 0.0005 < median_ratio < 0.005:
                # measurement ≈ coord / 1000 → coords are mm, measurements are m
                logger.info(
                    f"Scale detection: dimension calibration ratio={median_ratio:.4f} "
                    f"({len(ratios)} dims) → scale=0.001 (method: dimension calibration, "
                    f"coords in mm)"
                )
                return 0.001
            elif 0.5 < median_ratio < 2.0:
                # ratio ≈ 1.0 → coords and measurements in same unit.
                # Determine which unit by examining measurement values:
                # - If typical measurements are 10-100 → likely cm (10cm-1m beams)
                # - If typical measurements are 100-1000 → likely mm
                # - If typical measurements are 0.1-10 → likely meters
                median_meas = sorted([d.measurement for d in parse.dimensions
                                      if d.measurement > 0])[len(ratios) // 2]
                if 5 < median_meas < 200:
                    # Measurements like 50, 60, 100 → centimeters
                    logger.info(
                        f"Scale detection: ratio≈1.0, median_meas={median_meas:.1f} "
                        f"→ scale=0.01 (method: dimension calibration, coords in cm)"
                    )
                    return 0.01
                elif median_meas >= 200:
                    logger.info(
                        f"Scale detection: ratio≈1.0, median_meas={median_meas:.1f} "
                        f"→ scale=0.001 (method: dimension calibration, coords in mm)"
                    )
                    return 0.001
                else:
                    logger.info(
                        f"Scale detection: ratio≈1.0, median_meas={median_meas:.2f} "
                        f"→ scale=1.0 (method: dimension calibration, coords in m)"
                    )
                    return 1.0

    # --- Method 3: Coordinate range heuristic (improved) ---
    # Use the shorter dimension (Y typically) to avoid multi-view X inflation
    min_range = min(x_range, y_range)
    if min_range > 500:
        # Short dimension > 500 → not meters (500m building is unrealistic)
        # Distinguish cm vs mm by short dimension:
        # - cm: short dim 500-5000 (5m-50m buildings)
        # - mm: short dim 5000-50000 (5m-50m buildings)
        if min_range > 5000:
            scale = 0.001  # millimeters
            logger.info(
                f"Scale detection: min_range={min_range:.1f} > 5000 → scale=0.001 "
                f"(method: range heuristic, likely mm)"
            )
        else:
            scale = 0.01  # centimeters
            logger.info(
                f"Scale detection: min_range={min_range:.1f} in 500-5000 → scale=0.01 "
                f"(method: range heuristic, likely cm)"
            )
        return scale
    elif coord_range > 5.0:
        logger.info(
            f"Scale detection: coord_range={coord_range:.1f} > 5.0 → scale=1.0 "
            f"(method: range heuristic, likely meters)"
        )
        return 1.0
    else:
        scale = parse.detected_scale or DEFAULT_SCALE
        logger.info(
            f"Scale detection: coord_range={coord_range:.1f} <= 5.0 → scale={scale} "
            f"(method: text scale / default)"
        )
        return scale


def run_pipeline(
    filepath: str,
    scale_override: Optional[float] = None,
    mode: str = "price",
    inventory_name: Optional[str] = None,
    branch_id: Optional[str] = None,
) -> PipelineResult:
    # Stage 0: Load learning store for accumulated knowledge (per-branch when
    # branch_id is provided, so each locadora unit keeps its own corrections).
    store = LearningStore(branch_id=branch_id)
    known_beam_layers = store.get_known_beam_layers() if store.run_count > 0 else {}
    known_pillar_layers = store.get_known_pillar_layers() if store.run_count > 0 else {}
    learned_section_height = store.get_default_section_height() if store.run_count > 0 else None
    learned_pe_direito = store.get_pe_direito_history() if store.run_count > 0 else None

    density_correction = (
        store.get_shore_density_correction() if store.run_count > 0 else 1.0
    )
    validated_layers = (
        store.get_validated_layer_map() if store.run_count > 0 else {}
    )
    for layer, etype in validated_layers.items():
        if etype == "beam":
            known_beam_layers[layer] = 1.0

    inventory = None
    if mode == "inventory":
        try:
            from src.engine.inventory import load_inventory
            inventory = load_inventory(inventory_name or "orguel_sjc")
        except Exception as e:
            logger.warning(f"Inventory load failed (falling back to price mode): {e}")

    if store.run_count > 0:
        logger.info(
            f"Learning data loaded: {store.run_count} runs, "
            f"{len(known_beam_layers)} beam layers, "
            f"{len(known_pillar_layers)} pillar layers, "
            f"density_correction={density_correction:.2f}"
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

    # Stage 1.7: Sistema estrutural — passo zero da cadeia (manual §5.1,
    # pendencia 28). Deteccao textual aqui; contagens geometricas chegam
    # depois da classificacao de elementos (refinamento futuro).
    structural_system = detect_structural_system(
        texts=[t.content for t in parse.texts],
        construction_type=classification.construction_type,
    )
    logger.info(
        f"Sistema estrutural: {structural_system.system.value} "
        f"({structural_system.confidence:.0%}) -> "
        f"roteamento {structural_system.routing.value}"
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

    # Sistema estrutural no relatorio (manual §5.1: registrar sistema,
    # fonte da deteccao e score; pendencias viram avisos rastreaveis).
    warnings.append(
        f"Sistema estrutural: {structural_system.system.value} "
        f"({structural_system.confidence:.0%}) — "
        f"roteamento: {structural_system.routing.value}"
    )
    warnings.extend(structural_system.signals)
    warnings.extend(structural_system.pendencias)
    if structural_system.routing == SystemRouting.BLOCKED:
        warnings.append(
            "BLOQUEIO (manual §5.1): sistema fora de escopo do Escora.AI — "
            "saida automatica nao deve ser emitida como projeto executivo; "
            "encaminhar para revisao de engenharia."
        )

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
    if levels:
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
                    "cx": r.cx * scale, "cy": r.cy * scale,
                    "width": r.width * scale, "height": r.height * scale,
                    "area": r.area * scale * scale, "layer": r.layer,
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
            layer_types = _classify_layers(seg, scale=scale)
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

        # Collect hatches and closed polylines for direct slab boundary detection.
        # Scale points from raw DXF units to meters (same as beam segments).
        all_hatches = []
        all_polylines = []
        for seg in level_segments:
            for h in seg.hatches:
                all_hatches.append({
                    "points": [(x * scale, y * scale) for x, y in h.points],
                    "layer": h.layer,
                    "pattern_name": h.pattern_name,
                    "is_solid": h.is_solid,
                    "area": h.area * scale * scale,
                })
            for pl in seg.polylines:
                all_polylines.append({
                    "points": [(x * scale, y * scale) for x, y in pl.points],
                    "layer": pl.layer,
                    "is_closed": pl.is_closed,
                })

        # Colecta textos crus (TEXT/MTEXT) para extração de rótulos de cômodo
        # e nomes estruturais (L3, QUARTO 1…) próximos a cada painel de laje.
        all_texts: List[dict] = []
        for seg in level_segments:
            for t in seg.texts:
                all_texts.append({
                    "text": t.content,
                    "position": (t.x * scale, t.y * scale),
                    "layer": t.layer,
                })

        try:
            if not (all_elements or all_beam_layer_segs or all_hatches or all_polylines):
                raise ValueError(
                    "nenhum elemento estrutural, eixo de viga, hatch ou contorno de laje "
                    "foi classificado na planta principal"
                )

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
                shaft_diagonals=parse.diagonals,
                shaft_texts=parse.texts,
                density_correction=density_correction,
                mode=mode,
                inventory=inventory,
                text_entities=all_texts,
            )
            # A1: Resumo agregado por categoria para diagnóstico rápido.
            # Em projetos TQS com layers numéricos a classificação por keyword
            # nunca dispara e só geometria recategoriza — esta linha permite
            # ao usuário detectar se o pipeline perdeu algum beiral/balanço.
            # INSERIDA ANTES das warnings de cálculo para garantir visibilidade
            # mesmo quando há centenas de warnings ML/torre.
            diagnostic_lines: List[str] = []
            if calculation.slab_results:
                from collections import Counter as _Counter
                cat_counts = _Counter(
                    sr.category for sr in calculation.slab_results
                )
                diagnostic_lines.append(
                    "Painéis: "
                    f"{cat_counts.get('laje', 0)} lajes · "
                    f"{cat_counts.get('beiral', 0)} beirais · "
                    f"{cat_counts.get('platibanda', 0)} platibandas · "
                    f"{cat_counts.get('balanco', 0)} balanços · "
                    f"{cat_counts.get('cantilever', 0)} cantilevers"
                )
            # A2 em destaque: linhas de eixo e strips descartados vêm de
            # calculation.warnings e devem aparecer no topo também.
            for w in list(calculation.warnings):
                if w.startswith("Painéis descartados") or w.endswith(
                    "descartadas do cálculo"
                ):
                    diagnostic_lines.append(w)
            # Prepend diagnostics, then append the full calculation warnings
            warnings[:0] = diagnostic_lines
            warnings.extend(calculation.warnings)
        except Exception as e:
            logger.exception("Calculation stage failed")
            warnings.append(f"Cálculo falhou: {e}")
    else:
        warnings.append("Nenhum nível/planta principal foi identificado no DXF")

    result = PipelineResult(
        filename=parse.filename,
        scale=scale,
        construction_type=classification.construction_type.value,
        slab_type=classification.slab_type.value,
        levels=levels,
        warnings=warnings,
        calculation=calculation,
    )

    # Stage 6: Rule verification (feature flag: ESCORA_RUN_RULES, default on)
    import os
    if os.environ.get("ESCORA_RUN_RULES", "1") != "0" and result.calculation is not None:
        try:
            from src.rules import REGISTRY
            from src.rules.project import RuleProject
            rule_project = RuleProject.from_pipeline_result(result)
            result.violations = REGISTRY.check_all(rule_project)
        except Exception as e:
            logger.warning(f"Rule verification failed (non-fatal): {e}")

    # Stage 7: Learning — save what we learned from this run
    try:
        learn_and_save(result, level_segments=level_segments, store=store, source_dxf_path=filepath)
    except Exception as e:
        logger.warning(f"Learning stage failed (non-fatal): {e}")

    return result
