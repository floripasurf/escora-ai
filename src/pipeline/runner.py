"""Pipeline runner: orchestrates Stages 1-4 sequentially.

Stage 5 (validation/preview) and Stage 6 (learning) are handled
by the API layer, not the runner, since they require user interaction.
"""

from typing import List, Optional
from src.pipeline.stage_parse import parse_dxf
from src.pipeline.stage_segment import segment_by_level
from src.pipeline.stage_classify import classify_elements
from src.pipeline.stage_metadata import extract_pe_direito, extract_level_height
from src.models.pipeline_models import LevelGroup, PipelineResult


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
    # Stage 1: Parse
    parse = parse_dxf(filepath)

    scale = scale_override or _detect_coordinate_scale(parse)

    # Stage 2: Segment by level
    level_segments = segment_by_level(parse)

    # Stage 3 + 4: Classify + metadata for each level
    levels: List[LevelGroup] = []
    warnings: List[str] = []

    for seg in level_segments:
        elements = classify_elements(seg, scale=scale)

        pe_direito = extract_pe_direito(seg.texts)
        level_height = extract_level_height(seg.texts)

        if pe_direito is None:
            warnings.append(f"Pe-direito nao encontrado no nivel {seg.level_name}")

        level = LevelGroup(
            level_name=seg.level_name,
            level_height_m=level_height,
            pe_direito_m=pe_direito,
            elements=elements,
        )
        levels.append(level)

    return PipelineResult(
        filename=parse.filename,
        scale=scale,
        levels=levels,
        warnings=warnings,
    )
