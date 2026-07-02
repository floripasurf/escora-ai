"""Gerador de planta arquitetonica DXF para alvenaria estrutural.

Layers seguem convencao ABNT:
    ARQ-PAR-ESTRU  -- paredes estruturais (traco grosso)
    ARQ-PAR-VEDA   -- paredes de vedacao (traco fino)
    ARQ-ESQ-PORTA  -- portas (arco de abertura)
    ARQ-ESQ-JANELA -- janelas (dupla linha)
    ARQ-COT        -- cotas/dimensoes
    ARQ-TEXTO      -- textos e rotulos
    ARQ-HATCH      -- hachuras de piso

Referencia: NBR 6492:1994 -- Representacao de projetos de arquitetura
"""

import math
import ezdxf
import logging
from pathlib import Path

from src.models.masonry import FloorPlan, Wall, WallOpening, Room, OpeningType

logger = logging.getLogger(__name__)

# Layer colors (AutoCAD color index)
COLOR_WALL_STRUCT = 7    # White -- structural walls
COLOR_WALL_FILL = 253    # Dark gray -- non-structural
COLOR_DOOR = 1           # Red
COLOR_WINDOW = 5         # Blue
COLOR_DIM = 3            # Green
COLOR_TEXT = 8            # Gray
COLOR_HATCH = 251        # Light gray
COLOR_ROOM_LABEL = 4     # Cyan

# Drawing parameters
WALL_LINE_WIDTH = 0.0    # Will use layer lineweight instead
TEXT_HEIGHT = 0.12        # m
DIM_TEXT_HEIGHT = 0.08    # m
DOOR_ARC_SEGMENTS = 32


def _ensure_layer(doc, name: str, color: int, lineweight: int = -1) -> None:
    """Cria layer se nao existir."""
    if name not in doc.layers:
        attrs = {"color": color}
        if lineweight >= 0:
            attrs["lineweight"] = lineweight
        doc.layers.add(name, **attrs)


def generate_architectural_dxf(
    floor_plan: FloorPlan,
    output_path: str,
    scale: float = 1.0,
    draw_dimensions: bool = True,
    draw_hatches: bool = True,
) -> str:
    """Gera planta arquitetonica DXF.

    Args:
        floor_plan: Planta com rooms, walls e openings
        output_path: Caminho do arquivo de saida
        scale: Fator de escala (1.0 = metros)
        draw_dimensions: Se True, adiciona cotas
        draw_hatches: Se True, adiciona hachuras de piso

    Returns:
        Caminho do arquivo salvo
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Create layers
    _ensure_layer(doc, "ARQ-PAR-ESTRU", COLOR_WALL_STRUCT, lineweight=50)
    _ensure_layer(doc, "ARQ-PAR-VEDA", COLOR_WALL_FILL, lineweight=25)
    _ensure_layer(doc, "ARQ-ESQ-PORTA", COLOR_DOOR)
    _ensure_layer(doc, "ARQ-ESQ-JANELA", COLOR_WINDOW)
    _ensure_layer(doc, "ARQ-COT", COLOR_DIM)
    _ensure_layer(doc, "ARQ-TEXTO", COLOR_TEXT)
    _ensure_layer(doc, "ARQ-HATCH", COLOR_HATCH)
    _ensure_layer(doc, "ARQ-COMODO", COLOR_ROOM_LABEL)

    # Draw walls
    for wall in floor_plan.walls:
        _draw_wall(msp, wall)

    # Draw openings
    for wall in floor_plan.walls:
        for opening in wall.openings:
            if opening.type == OpeningType.DOOR:
                _draw_door(msp, wall, opening)
            else:
                _draw_window(msp, wall, opening)

    # Draw room labels
    for room in floor_plan.rooms:
        _draw_room_label(msp, room)

    # Draw dimensions
    if draw_dimensions:
        _draw_dimensions(msp, floor_plan)

    # Save
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out))

    logger.info(f"Planta arquitetonica salva: {out}")
    return str(out)


def _wall_direction(wall: Wall):
    """Retorna vetor direcao e normal da parede."""
    dx = wall.end[0] - wall.start[0]
    dy = wall.end[1] - wall.start[1]
    length = math.hypot(dx, dy)
    if length < 0.001:
        return (1, 0), (0, 1), 0
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    return (ux, uy), (nx, ny), length


def _draw_wall(msp, wall: Wall) -> None:
    """Desenha parede como retangulo (duas linhas paralelas com preenchimento).

    Paredes estruturais: traco grosso, preenchimento solido
    Paredes de vedacao: traco fino, sem preenchimento
    """
    layer = "ARQ-PAR-ESTRU" if wall.is_structural else "ARQ-PAR-VEDA"
    (ux, uy), (nx, ny), length = _wall_direction(wall)

    if length < 0.001:
        return

    ht = wall.thickness_m / 2.0

    # Four corners of the wall rectangle
    x1, y1 = wall.start
    x2, y2 = wall.end

    corners = [
        (x1 + nx * ht, y1 + ny * ht),
        (x2 + nx * ht, y2 + ny * ht),
        (x2 - nx * ht, y2 - ny * ht),
        (x1 - nx * ht, y1 - ny * ht),
    ]

    msp.add_lwpolyline(
        corners, close=True,
        dxfattribs={"layer": layer},
    )

    # Add hatch for structural walls
    if wall.is_structural:
        try:
            hatch = msp.add_hatch(dxfattribs={"layer": layer, "color": 254})
            hatch.paths.add_polyline_path(
                [c + (0,) for c in corners] + [corners[0] + (0,)],
                is_closed=True,
            )
            hatch.set_pattern_fill("ANSI31", scale=0.02)
        except Exception:
            pass


def _draw_door(msp, wall: Wall, opening: WallOpening) -> None:
    """Desenha porta com arco de abertura (convencao NBR 6492).

    O arco indica o sentido de abertura da folha.
    """
    (ux, uy), (nx, ny), wall_length = _wall_direction(wall)

    # Opening position along the wall
    pos = opening.position_m
    w = opening.width_m

    # Center of opening along wall axis
    cx = wall.start[0] + ux * (pos + w / 2)
    cy = wall.start[1] + uy * (pos + w / 2)

    # Gap in wall (clear the wall lines at opening)
    # Draw the opening line (threshold)
    p1 = (wall.start[0] + ux * pos, wall.start[1] + uy * pos)
    p2 = (wall.start[0] + ux * (pos + w), wall.start[1] + uy * (pos + w))

    # Door leaf line
    msp.add_line(
        p1, p2,
        dxfattribs={"layer": "ARQ-ESQ-PORTA"},
    )

    # Arc of door swing (90 degrees)
    # Arc from the hinge point, radius = door width
    angle_base = math.degrees(math.atan2(uy, ux))
    # Draw arc perpendicular to wall
    arc_start_angle = angle_base
    arc_end_angle = angle_base + 90

    msp.add_arc(
        center=p1,
        radius=w,
        start_angle=arc_start_angle,
        end_angle=arc_end_angle,
        dxfattribs={"layer": "ARQ-ESQ-PORTA"},
    )


def _draw_window(msp, wall: Wall, opening: WallOpening) -> None:
    """Desenha janela com dupla linha (convencao NBR 6492).

    Janelas sao representadas por duas linhas paralelas dentro da parede.
    """
    (ux, uy), (nx, ny), wall_length = _wall_direction(wall)

    pos = opening.position_m
    w = opening.width_m
    ht = 0.03  # half thickness of window symbol

    # Window endpoints along wall
    p1 = (wall.start[0] + ux * pos, wall.start[1] + uy * pos)
    p2 = (wall.start[0] + ux * (pos + w), wall.start[1] + uy * (pos + w))

    # Two parallel lines (window symbol)
    for sign in [1, -1]:
        lp1 = (p1[0] + nx * ht * sign, p1[1] + ny * ht * sign)
        lp2 = (p2[0] + nx * ht * sign, p2[1] + ny * ht * sign)
        msp.add_line(
            lp1, lp2,
            dxfattribs={"layer": "ARQ-ESQ-JANELA"},
        )

    # End lines (close the window symbol)
    for p in [p1, p2]:
        e1 = (p[0] + nx * ht, p[1] + ny * ht)
        e2 = (p[0] - nx * ht, p[1] - ny * ht)
        msp.add_line(e1, e2, dxfattribs={"layer": "ARQ-ESQ-JANELA"})


def _draw_room_label(msp, room: Room) -> None:
    """Desenha rotulo do comodo no centro com nome e area."""
    if len(room.polygon) < 3:
        return

    # Calculate centroid
    cx = sum(p[0] for p in room.polygon) / len(room.polygon)
    cy = sum(p[1] for p in room.polygon) / len(room.polygon)

    # Room name
    msp.add_text(
        room.name,
        height=TEXT_HEIGHT,
        dxfattribs={"layer": "ARQ-COMODO"},
    ).set_placement((cx - 0.3, cy + 0.08))

    # Area
    area = room.area_m2
    msp.add_text(
        f"A={area:.1f}m\u00b2",
        height=TEXT_HEIGHT * 0.7,
        dxfattribs={"layer": "ARQ-COMODO"},
    ).set_placement((cx - 0.3, cy - 0.15))


def _draw_dimensions(msp, floor_plan: FloorPlan) -> None:
    """Desenha cotas externas da planta.

    Cotas horizontais abaixo da planta, cotas verticais a esquerda.
    """
    if not floor_plan.walls:
        return

    # Overall dimensions
    offset = 0.50  # distance from building edge
    w = floor_plan.width_m
    d = floor_plan.depth_m

    # Bottom horizontal dimension
    msp.add_line(
        (0, -offset), (w, -offset),
        dxfattribs={"layer": "ARQ-COT"},
    )
    # Ticks
    for x in [0, w]:
        msp.add_line(
            (x, -offset - 0.05), (x, -offset + 0.05),
            dxfattribs={"layer": "ARQ-COT"},
        )
    # Label
    msp.add_text(
        f"{w:.2f}",
        height=DIM_TEXT_HEIGHT,
        dxfattribs={"layer": "ARQ-COT"},
    ).set_placement((w / 2 - 0.15, -offset - 0.15))

    # Left vertical dimension
    msp.add_line(
        (-offset, 0), (-offset, d),
        dxfattribs={"layer": "ARQ-COT"},
    )
    for y in [0, d]:
        msp.add_line(
            (-offset - 0.05, y), (-offset + 0.05, y),
            dxfattribs={"layer": "ARQ-COT"},
        )
    msp.add_text(
        f"{d:.2f}",
        height=DIM_TEXT_HEIGHT,
        rotation=90,
        dxfattribs={"layer": "ARQ-COT"},
    ).set_placement((-offset - 0.15, d / 2 - 0.15))
