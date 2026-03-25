"""Stage 1: Raw DXF entity extraction.

Reads any DXF file and extracts all entities with their attributes,
layer names, coordinates, and nearby text annotations.
Detects drawing scale from text annotations.
"""

import ezdxf
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from src.parser.scale_detector import detect_scale_from_texts


@dataclass
class TextEntity:
    content: str
    x: float
    y: float
    layer: str


@dataclass
class SegmentEntity:
    """A line segment (horizontal or vertical)."""
    type: str  # "H" or "V"
    x: float = 0.0   # for V segments
    y: float = 0.0   # for H segments
    x_min: float = 0.0
    x_max: float = 0.0
    y_min: float = 0.0
    y_max: float = 0.0
    layer: str = ""


@dataclass
class RectEntity:
    """A closed rectangle (potential pillar)."""
    cx: float
    cy: float
    width: float
    height: float
    area: float
    layer: str = ""


@dataclass
class PolylineEntity:
    """A closed polyline (potential slab boundary)."""
    points: List[Tuple[float, float]]
    layer: str = ""
    is_closed: bool = False


@dataclass
class ParseResult:
    filename: str
    layers: List[str]
    detected_scale: Optional[float]
    texts: List[TextEntity] = field(default_factory=list)
    segments: List[SegmentEntity] = field(default_factory=list)
    rects: List[RectEntity] = field(default_factory=list)
    polylines: List[PolylineEntity] = field(default_factory=list)
    raw_entities: List[dict] = field(default_factory=list)


def parse_dxf(filepath: str) -> ParseResult:
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    filename = Path(filepath).name
    layers = [layer.dxf.name for layer in doc.layers]

    texts: List[TextEntity] = []
    segments: List[SegmentEntity] = []
    rects: List[RectEntity] = []
    polylines: List[PolylineEntity] = []
    raw_entities: List[dict] = []

    for entity in msp:
        etype = entity.dxftype()
        layer = entity.dxf.layer

        raw_entities.append({"type": etype, "layer": layer})

        if etype in ("TEXT", "MTEXT"):
            content = entity.dxf.text if etype == "TEXT" else entity.text
            insert = entity.dxf.insert if hasattr(entity.dxf, "insert") else (0, 0, 0)
            texts.append(TextEntity(
                content=content,
                x=insert[0],
                y=insert[1],
                layer=layer,
            ))

        elif etype == "LINE":
            x1, y1 = entity.dxf.start.x, entity.dxf.start.y
            x2, y2 = entity.dxf.end.x, entity.dxf.end.y
            if abs(y1 - y2) < 0.01:  # horizontal
                segments.append(SegmentEntity(
                    type="H", y=(y1 + y2) / 2,
                    x_min=min(x1, x2), x_max=max(x1, x2), layer=layer,
                ))
            elif abs(x1 - x2) < 0.01:  # vertical
                segments.append(SegmentEntity(
                    type="V", x=(x1 + x2) / 2,
                    y_min=min(y1, y2), y_max=max(y1, y2), layer=layer,
                ))

        elif etype == "SOLID":
            pts = [entity.dxf.vtx0, entity.dxf.vtx1, entity.dxf.vtx2, entity.dxf.vtx3]
            xs = [p.x for p in pts]
            ys = [p.y for p in pts]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if w > 0 and h > 0:
                rects.append(RectEntity(
                    cx=(min(xs) + max(xs)) / 2,
                    cy=(min(ys) + max(ys)) / 2,
                    width=w, height=h, area=w * h, layer=layer,
                ))

        elif etype in ("LWPOLYLINE", "POLYLINE"):
            if etype == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in entity.get_points(format="xy")]
                closed = entity.closed
            else:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                closed = entity.is_closed
            if len(pts) >= 2:
                polylines.append(PolylineEntity(
                    points=pts, layer=layer, is_closed=closed,
                ))
                # Also extract as line segments if 2-point polyline
                if len(pts) == 2:
                    x1, y1 = pts[0]
                    x2, y2 = pts[1]
                    if abs(y1 - y2) < 0.01:
                        segments.append(SegmentEntity(
                            type="H", y=(y1 + y2) / 2,
                            x_min=min(x1, x2), x_max=max(x1, x2), layer=layer,
                        ))
                    elif abs(x1 - x2) < 0.01:
                        segments.append(SegmentEntity(
                            type="V", x=(x1 + x2) / 2,
                            y_min=min(y1, y2), y_max=max(y1, y2), layer=layer,
                        ))

    # Detect scale
    text_contents = [t.content for t in texts]
    detected_scale = detect_scale_from_texts(text_contents)

    return ParseResult(
        filename=filename,
        layers=layers,
        detected_scale=detected_scale,
        texts=texts,
        segments=segments,
        rects=rects,
        polylines=polylines,
        raw_entities=raw_entities,
    )
