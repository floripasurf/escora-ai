"""Stage 1: Raw DXF entity extraction.

Reads any DXF file and extracts all entities with their attributes,
layer names, coordinates, and nearby text annotations.
Detects drawing scale from text annotations.

Supported entity types:
- LINE, SOLID, CIRCLE, TEXT, MTEXT (original)
- LWPOLYLINE, POLYLINE — now decomposed into H/V segments for ALL points
- INSERT — resolved via virtual_entities() + ATTRIB extraction
- HATCH — boundary polygons extracted
- DIMENSION — measurement values + positions extracted
"""

import ezdxf
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from src.parser.scale_detector import detect_scale_from_texts

logger = logging.getLogger(__name__)

# Tolerance for classifying lines as horizontal/vertical
HV_TOLERANCE = 0.01


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
class CircleEntity:
    """A circle (potential circular column)."""
    cx: float
    cy: float
    radius: float
    layer: str = ""


@dataclass
class PolylineEntity:
    """A closed polyline (potential slab boundary)."""
    points: List[Tuple[float, float]]
    layer: str = ""
    is_closed: bool = False


@dataclass
class HatchEntity:
    """A hatched area boundary (potential slab confirmation)."""
    points: List[Tuple[float, float]]
    pattern_name: str
    is_solid: bool
    layer: str = ""
    area: float = 0.0


@dataclass
class DimensionEntity:
    """A dimension measurement from the drawing."""
    measurement: float
    text: str
    x: float
    y: float
    dim_type: int  # 0=linear, 1=aligned, 2=angular, etc.
    layer: str = ""


@dataclass
class ArcEntity:
    """An arc entity (potential curved structural element or corner fillet)."""
    cx: float
    cy: float
    radius: float
    start_angle: float  # degrees
    end_angle: float    # degrees
    layer: str = ""


@dataclass
class ParseResult:
    filename: str
    layers: List[str]
    detected_scale: Optional[float]
    texts: List[TextEntity] = field(default_factory=list)
    segments: List[SegmentEntity] = field(default_factory=list)
    rects: List[RectEntity] = field(default_factory=list)
    polylines: List[PolylineEntity] = field(default_factory=list)
    circles: List[CircleEntity] = field(default_factory=list)
    hatches: List[HatchEntity] = field(default_factory=list)
    dimensions: List[DimensionEntity] = field(default_factory=list)
    arcs: List[ArcEntity] = field(default_factory=list)
    raw_entities: List[dict] = field(default_factory=list)


def _add_line_segment(
    x1: float, y1: float, x2: float, y2: float,
    layer: str, segments: List[SegmentEntity],
) -> None:
    """Add a line as H or V segment if it's axis-aligned."""
    if abs(y1 - y2) < HV_TOLERANCE:  # horizontal
        segments.append(SegmentEntity(
            type="H", y=(y1 + y2) / 2,
            x_min=min(x1, x2), x_max=max(x1, x2), layer=layer,
        ))
    elif abs(x1 - x2) < HV_TOLERANCE:  # vertical
        segments.append(SegmentEntity(
            type="V", x=(x1 + x2) / 2,
            y_min=min(y1, y2), y_max=max(y1, y2), layer=layer,
        ))


def _decompose_polyline_segments(
    pts: List[Tuple[float, float]], closed: bool, layer: str,
    segments: List[SegmentEntity],
) -> None:
    """Decompose ALL consecutive point pairs of a polyline into H/V segments.

    Previously only 2-point polylines were decomposed. Now handles N-point
    polylines (beam outlines, complex shapes), extracting every axis-aligned edge.
    """
    n = len(pts)
    if n < 2:
        return
    # Walk consecutive pairs
    for i in range(n - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        _add_line_segment(x1, y1, x2, y2, layer, segments)
    # If closed, also connect last → first
    if closed and n >= 3:
        x1, y1 = pts[-1]
        x2, y2 = pts[0]
        _add_line_segment(x1, y1, x2, y2, layer, segments)


def _extract_text(entity, layer: str) -> Optional[TextEntity]:
    """Extract text content and position from TEXT or MTEXT entity."""
    etype = entity.dxftype()
    try:
        content = entity.dxf.text if etype == "TEXT" else entity.text
        if not content or not content.strip():
            return None
        insert = entity.dxf.insert if hasattr(entity.dxf, "insert") else (0, 0, 0)
        return TextEntity(content=content, x=insert[0], y=insert[1], layer=layer)
    except Exception:
        return None


def _process_insert(
    entity, layer: str,
    texts: List[TextEntity], segments: List[SegmentEntity],
    rects: List[RectEntity], circles: List[CircleEntity],
    polylines: List[PolylineEntity],
) -> None:
    """Resolve INSERT block reference into constituent entities.

    Uses virtual_entities() for non-destructive geometry extraction.
    Also extracts ATTRIB values as text annotations.
    """
    try:
        for sub in entity.virtual_entities():
            sub_type = sub.dxftype()
            # Sub-entities on layer "0" inherit the INSERT's layer.
            # Blocks defined on layer 0 adopt the insert's layer in AutoCAD;
            # ezdxf virtual_entities doesn't always replicate this behavior.
            raw_sub_layer = sub.dxf.layer if hasattr(sub.dxf, "layer") else "0"
            sub_layer = layer if raw_sub_layer == "0" else raw_sub_layer

            if sub_type in ("TEXT", "MTEXT"):
                te = _extract_text(sub, sub_layer)
                if te:
                    texts.append(te)

            elif sub_type == "LINE":
                x1, y1 = sub.dxf.start.x, sub.dxf.start.y
                x2, y2 = sub.dxf.end.x, sub.dxf.end.y
                _add_line_segment(x1, y1, x2, y2, sub_layer, segments)

            elif sub_type == "SOLID":
                try:
                    pts = [sub.dxf.vtx0, sub.dxf.vtx1, sub.dxf.vtx2, sub.dxf.vtx3]
                    xs = [p.x for p in pts]
                    ys = [p.y for p in pts]
                    w = max(xs) - min(xs)
                    h = max(ys) - min(ys)
                    if w > 0 and h > 0:
                        rects.append(RectEntity(
                            cx=(min(xs) + max(xs)) / 2, cy=(min(ys) + max(ys)) / 2,
                            width=w, height=h, area=w * h, layer=sub_layer,
                        ))
                except Exception:
                    pass

            elif sub_type == "CIRCLE":
                try:
                    circles.append(CircleEntity(
                        cx=sub.dxf.center.x, cy=sub.dxf.center.y,
                        radius=sub.dxf.radius, layer=sub_layer,
                    ))
                except Exception:
                    pass

            elif sub_type in ("LWPOLYLINE", "POLYLINE"):
                try:
                    if sub_type == "LWPOLYLINE":
                        pts = [(p[0], p[1]) for p in sub.get_points(format="xy")]
                        closed = sub.closed
                    else:
                        pts = [(v.dxf.location.x, v.dxf.location.y) for v in sub.vertices]
                        closed = sub.is_closed
                    if len(pts) >= 2:
                        polylines.append(PolylineEntity(points=pts, layer=sub_layer, is_closed=closed))
                        _decompose_polyline_segments(pts, closed, sub_layer, segments)
                except Exception:
                    pass

    except Exception as e:
        logger.debug(f"INSERT virtual_entities failed: {e}")

    # Extract ATTRIB values (element names like P1, V12 inside blocks)
    try:
        for attrib in entity.attribs:
            text = attrib.dxf.text
            if text and text.strip():
                texts.append(TextEntity(
                    content=text,
                    x=attrib.dxf.insert.x,
                    y=attrib.dxf.insert.y,
                    layer=layer,
                ))
    except Exception:
        pass


def _process_hatch(
    entity, layer: str, hatches: List[HatchEntity],
) -> None:
    """Extract HATCH boundary polygons."""
    try:
        pattern_name = entity.dxf.pattern_name if hasattr(entity.dxf, "pattern_name") else ""
        is_solid = bool(entity.dxf.solid_fill) if hasattr(entity.dxf, "solid_fill") else False

        for path in entity.paths:
            points: List[Tuple[float, float]] = []
            try:
                # Polyline boundary path
                if hasattr(path, "vertices") and path.vertices:
                    points = [(v.x, v.y) for v in path.vertices]
                # Edge boundary path
                elif hasattr(path, "edges"):
                    for edge in path.edges:
                        if hasattr(edge, "start") and hasattr(edge, "end"):
                            points.append((edge.start[0], edge.start[1]))
                            points.append((edge.end[0], edge.end[1]))
            except Exception:
                continue

            if len(points) >= 3:
                # Calculate approximate area using shoelace formula
                area = 0.0
                n = len(points)
                for i in range(n):
                    j = (i + 1) % n
                    area += points[i][0] * points[j][1]
                    area -= points[j][0] * points[i][1]
                area = abs(area) / 2.0

                hatches.append(HatchEntity(
                    points=points, pattern_name=pattern_name,
                    is_solid=is_solid, layer=layer, area=area,
                ))
    except Exception as e:
        logger.debug(f"HATCH extraction failed: {e}")


def _process_dimension(
    entity, layer: str, dimensions: List[DimensionEntity],
) -> None:
    """Extract DIMENSION measurement values and positions."""
    try:
        measurement = entity.dxf.actual_measurement if hasattr(entity.dxf, "actual_measurement") else 0.0
        text_override = entity.dxf.text if hasattr(entity.dxf, "text") else ""

        # Use override text if present, otherwise format measurement
        if text_override and text_override not in ("", "<>"):
            display_text = text_override
        else:
            display_text = f"{measurement:.2f}"

        # Position: prefer text_midpoint, fallback to defpoint
        x, y = 0.0, 0.0
        if hasattr(entity.dxf, "text_midpoint"):
            x = entity.dxf.text_midpoint.x
            y = entity.dxf.text_midpoint.y
        elif hasattr(entity.dxf, "defpoint"):
            x = entity.dxf.defpoint.x
            y = entity.dxf.defpoint.y

        dim_type = entity.dimtype if hasattr(entity, "dimtype") else 0

        dimensions.append(DimensionEntity(
            measurement=measurement, text=display_text,
            x=x, y=y, dim_type=dim_type, layer=layer,
        ))
    except Exception as e:
        logger.debug(f"DIMENSION extraction failed: {e}")


def parse_dxf(filepath: str) -> ParseResult:
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    filename = Path(filepath).name
    layers = [layer.dxf.name for layer in doc.layers]

    texts: List[TextEntity] = []
    segments: List[SegmentEntity] = []
    rects: List[RectEntity] = []
    circles: List[CircleEntity] = []
    polylines: List[PolylineEntity] = []
    hatches: List[HatchEntity] = []
    dimensions: List[DimensionEntity] = []
    arcs: List[ArcEntity] = []
    raw_entities: List[dict] = []

    for entity in msp:
        etype = entity.dxftype()
        layer = entity.dxf.layer

        raw_entities.append({"type": etype, "layer": layer})

        if etype in ("TEXT", "MTEXT"):
            te = _extract_text(entity, layer)
            if te:
                texts.append(te)

        elif etype == "LINE":
            x1, y1 = entity.dxf.start.x, entity.dxf.start.y
            x2, y2 = entity.dxf.end.x, entity.dxf.end.y
            _add_line_segment(x1, y1, x2, y2, layer, segments)

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

        elif etype == "CIRCLE":
            circles.append(CircleEntity(
                cx=entity.dxf.center.x,
                cy=entity.dxf.center.y,
                radius=entity.dxf.radius,
                layer=layer,
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
                # Decompose ALL polyline edges into H/V segments (not just 2-point)
                _decompose_polyline_segments(pts, closed, layer, segments)

        elif etype == "INSERT":
            _process_insert(entity, layer, texts, segments, rects, circles, polylines)

        elif etype == "HATCH":
            _process_hatch(entity, layer, hatches)

        elif etype == "DIMENSION":
            _process_dimension(entity, layer, dimensions)

        elif etype == "ARC":
            try:
                arcs.append(ArcEntity(
                    cx=entity.dxf.center.x,
                    cy=entity.dxf.center.y,
                    radius=entity.dxf.radius,
                    start_angle=entity.dxf.start_angle,
                    end_angle=entity.dxf.end_angle,
                    layer=layer,
                ))
            except Exception:
                pass

    # Detect scale
    text_contents = [t.content for t in texts]
    detected_scale = detect_scale_from_texts(text_contents)

    logger.info(
        f"Parsed {filename}: {len(segments)} segments, {len(rects)} rects, "
        f"{len(circles)} circles, {len(texts)} texts, {len(hatches)} hatches, "
        f"{len(dimensions)} dimensions, {len(polylines)} polylines, {len(arcs)} arcs"
    )

    return ParseResult(
        filename=filename,
        layers=layers,
        detected_scale=detected_scale,
        texts=texts,
        segments=segments,
        rects=rects,
        circles=circles,
        polylines=polylines,
        hatches=hatches,
        dimensions=dimensions,
        arcs=arcs,
        raw_entities=raw_entities,
    )
