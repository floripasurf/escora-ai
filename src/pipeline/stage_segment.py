"""Stage 2: Segment DXF entities by floor level.

Searches for TEXT/MTEXT with level patterns (+1330, COBERTURA, TIPO 1, N+3.00).
For MVP, treats entire DXF as single level if no level text found.
Multi-level segmentation by spatial proximity is Fase 2.
"""

import re
from typing import List
from dataclasses import dataclass, field
from src.pipeline.stage_parse import ParseResult, TextEntity, SegmentEntity, RectEntity, CircleEntity, PolylineEntity

LEVEL_PATTERN = re.compile(
    r"(?:COBERTURA|COBERTA|TIPO\s*\d+|PAVT?\.?\s*\d+|"
    r"N[IÍ]VEL\s*[\+\-]?\s*[\d.]+|"
    r"[\+\-]\s*\d{2,}\.\d+|"
    r"N\s*[\+\-]\s*\d+\.?\d*)",
    re.IGNORECASE,
)


@dataclass
class LevelSegment:
    level_name: str
    level_height_m: float = 0.0
    texts: List[TextEntity] = field(default_factory=list)
    segments: List[SegmentEntity] = field(default_factory=list)
    rects: List[RectEntity] = field(default_factory=list)
    circles: List[CircleEntity] = field(default_factory=list)
    polylines: List[PolylineEntity] = field(default_factory=list)


def _extract_level_height(text: str) -> float:
    m = re.search(r"[\+\-]?\s*(\d{2,}\.?\d*)", text)
    if m:
        return float(m.group(1).replace(" ", ""))
    return 0.0


def segment_by_level(parse: ParseResult) -> List[LevelSegment]:
    # Find level annotations
    level_texts = []
    for t in parse.texts:
        if LEVEL_PATTERN.search(t.content):
            level_texts.append(t)

    if not level_texts:
        # Single level -- everything in one group
        seg = LevelSegment(
            level_name="DEFAULT",
            texts=parse.texts,
            segments=parse.segments,
            rects=parse.rects,
            circles=parse.circles,
            polylines=parse.polylines,
        )
        return [seg]

    # MVP: use first found level for the whole file
    # Multi-level spatial segmentation deferred to Fase 2
    first = level_texts[0]
    level_name = LEVEL_PATTERN.search(first.content).group(0).strip()
    level_height = _extract_level_height(first.content)

    seg = LevelSegment(
        level_name=level_name,
        level_height_m=level_height,
        texts=parse.texts,
        segments=parse.segments,
        rects=parse.rects,
        circles=parse.circles,
        polylines=parse.polylines,
    )
    return [seg]
