"""Gerador de planta estrutural DXF para alvenaria.

Layers:
    EST-PAREDE   -- paredes estruturais com marcacao de modulacao
    EST-CINTA    -- cintas de amarracao (respaldo + intermediaria)
    EST-VERGA    -- vergas e contravergas
    EST-FUND     -- fundacao (sapata corrida / radier)
    EST-FIADA    -- primeira fiada (layout de blocos)
    EST-TEXTO    -- textos e informacoes estruturais
    EST-CARGA    -- indicacao de cargas nas paredes

Referencia: NBR 15961-1:2011
"""

import math
import ezdxf
import logging
from pathlib import Path
from typing import List

from src.models.masonry import (
    Wall, Lintel, TieBeam, MasonryProject,
)

logger = logging.getLogger(__name__)

# Colors
COLOR_WALL = 7       # White
COLOR_CINTA = 3      # Green
COLOR_VERGA = 1      # Red
COLOR_FUND = 6       # Magenta
COLOR_FIADA = 5      # Blue
COLOR_TEXT = 8        # Gray
COLOR_CARGA = 4      # Cyan


def _ensure_layer(doc, name: str, color: int) -> None:
    if name not in doc.layers:
        doc.layers.add(name, color=color)


def generate_structural_dxf(
    project: MasonryProject,
    output_path: str,
) -> str:
    """Gera planta estrutural DXF.

    Args:
        project: Projeto com floor_plans, foundations, cargas calculadas
        output_path: Caminho de saida

    Returns:
        Caminho do arquivo salvo
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    _ensure_layer(doc, "EST-PAREDE", COLOR_WALL)
    _ensure_layer(doc, "EST-CINTA", COLOR_CINTA)
    _ensure_layer(doc, "EST-VERGA", COLOR_VERGA)
    _ensure_layer(doc, "EST-FUND", COLOR_FUND)
    _ensure_layer(doc, "EST-FIADA", COLOR_FIADA)
    _ensure_layer(doc, "EST-TEXTO", COLOR_TEXT)
    _ensure_layer(doc, "EST-CARGA", COLOR_CARGA)

    for floor_plan in project.floor_plans:
        y_offset = floor_plan.level * (floor_plan.depth_m + 2.0)

        # Draw structural walls
        for wall in floor_plan.walls:
            if wall.is_structural:
                _draw_structural_wall(msp, wall, y_offset)

        # Draw lintels
        for lintel in floor_plan.lintels:
            wall = _find_wall(floor_plan.walls, lintel.wall_id)
            if wall:
                _draw_lintel(msp, wall, lintel, y_offset)

        # Draw tie beams
        for tie_beam in floor_plan.tie_beams:
            _draw_tie_beam(msp, tie_beam, y_offset)

        # Draw load annotations
        for wall in floor_plan.walls:
            if wall.is_structural and wall.load_kn_per_m > 0:
                _draw_load_annotation(msp, wall, y_offset)

    # Draw foundations
    if project.foundations:
        fund_offset_y = -3.0  # below the floor plan
        _draw_foundations(msp, project, fund_offset_y)

    # Title block
    _draw_title(msp, project)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out))

    logger.info(f"Planta estrutural salva: {out}")
    return str(out)


def _draw_structural_wall(msp, wall: Wall, y_offset: float = 0.0) -> None:
    """Desenha parede estrutural com eixo e espessura."""
    dx = wall.end[0] - wall.start[0]
    dy = wall.end[1] - wall.start[1]
    length = math.hypot(dx, dy)
    if length < 0.001:
        return

    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    ht = wall.thickness_m / 2.0

    sx, sy = wall.start[0], wall.start[1] + y_offset
    ex, ey = wall.end[0], wall.end[1] + y_offset

    # Wall outline (filled rectangle)
    corners = [
        (sx + nx * ht, sy + ny * ht),
        (ex + nx * ht, ey + ny * ht),
        (ex - nx * ht, ey - ny * ht),
        (sx - nx * ht, sy - ny * ht),
    ]
    msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": "EST-PAREDE"})

    # Center axis (dashed)
    msp.add_line(
        (sx, sy), (ex, ey),
        dxfattribs={"layer": "EST-PAREDE", "linetype": "DASHED"},
    )

    # Wall ID label
    mid_x = (sx + ex) / 2
    mid_y = (sy + ey) / 2
    msp.add_text(
        wall.id,
        height=0.08,
        dxfattribs={"layer": "EST-TEXTO"},
    ).set_placement((mid_x + nx * ht * 1.5, mid_y + ny * ht * 1.5))


def _draw_lintel(msp, wall: Wall, lintel: Lintel, y_offset: float = 0.0) -> None:
    """Desenha verga/contraverga como retangulo hachurado sobre a abertura."""
    if lintel.opening_index >= len(wall.openings):
        return

    opening = wall.openings[lintel.opening_index]

    dx = wall.end[0] - wall.start[0]
    dy = wall.end[1] - wall.start[1]
    length = math.hypot(dx, dy)
    if length < 0.001:
        return

    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux

    # Position along wall
    apoio = 0.30
    start_pos = opening.position_m - apoio
    end_pos = opening.position_m + opening.width_m + apoio

    ht = wall.thickness_m / 2.0

    p1x = wall.start[0] + ux * start_pos
    p1y = wall.start[1] + uy * start_pos + y_offset
    p2x = wall.start[0] + ux * end_pos
    p2y = wall.start[1] + uy * end_pos + y_offset

    # Verga rectangle (along wall, slightly offset)
    offset = ht + 0.05
    v_corners = [
        (p1x + nx * offset, p1y + ny * offset),
        (p2x + nx * offset, p2y + ny * offset),
        (p2x + nx * (offset + lintel.height_m), p2y + ny * (offset + lintel.height_m)),
        (p1x + nx * (offset + lintel.height_m), p1y + ny * (offset + lintel.height_m)),
    ]
    msp.add_lwpolyline(v_corners, close=True, dxfattribs={"layer": "EST-VERGA"})

    # Label
    mid_x = (p1x + p2x) / 2
    mid_y = (p1y + p2y) / 2
    msp.add_text(
        f"V {lintel.span_m:.2f}m",
        height=0.06,
        dxfattribs={"layer": "EST-TEXTO"},
    ).set_placement((mid_x + nx * (offset + 0.18), mid_y + ny * (offset + 0.18)))


def _draw_tie_beam(msp, tie_beam: TieBeam, y_offset: float = 0.0) -> None:
    """Desenha cinta de amarracao como linha tracejada ao longo do percurso."""
    if len(tie_beam.path) < 2:
        return

    points = [(p[0], p[1] + y_offset) for p in tie_beam.path]

    msp.add_lwpolyline(
        points,
        dxfattribs={"layer": "EST-CINTA"},
    )

    # Label at first point
    msp.add_text(
        f"CINTA {tie_beam.level.upper()} ({tie_beam.rebar})",
        height=0.06,
        dxfattribs={"layer": "EST-TEXTO"},
    ).set_placement((points[0][0] + 0.1, points[0][1] + 0.1))


def _draw_load_annotation(msp, wall: Wall, y_offset: float = 0.0) -> None:
    """Anota a carga na parede."""
    mid_x = (wall.start[0] + wall.end[0]) / 2
    mid_y = (wall.start[1] + wall.end[1]) / 2 + y_offset

    dx = wall.end[0] - wall.start[0]
    dy = wall.end[1] - wall.start[1]
    length = math.hypot(dx, dy)
    if length < 0.001:
        return
    nx, ny = -(dy / length), dx / length

    offset = wall.thickness_m / 2.0 + 0.20

    msp.add_text(
        f"{wall.load_kn_per_m:.1f} kN/m",
        height=0.06,
        dxfattribs={"layer": "EST-CARGA"},
    ).set_placement((mid_x - nx * offset, mid_y - ny * offset))


def _draw_foundations(msp, project: MasonryProject, y_offset: float) -> None:
    """Desenha planta de fundacoes abaixo da planta do pavimento."""
    # Title
    msp.add_text(
        "FUNDACOES",
        height=0.15,
        dxfattribs={"layer": "EST-TEXTO"},
    ).set_placement((0, y_offset + 0.5))

    if not project.floor_plans:
        return

    floor = project.floor_plans[0]

    for i, wall in enumerate(floor.walls):
        if not wall.is_structural:
            continue
        if i >= len(project.foundations):
            break

        foundation = project.foundations[i] if i < len(project.foundations) else None
        if foundation is None:
            continue

        dx = wall.end[0] - wall.start[0]
        dy = wall.end[1] - wall.start[1]
        length = math.hypot(dx, dy)
        if length < 0.001:
            continue

        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux

        sx = wall.start[0]
        sy = wall.start[1] + y_offset
        ex = wall.end[0]
        ey = wall.end[1] + y_offset

        hw = foundation.width_m / 2.0

        corners = [
            (sx + nx * hw, sy + ny * hw),
            (ex + nx * hw, ey + ny * hw),
            (ex - nx * hw, ey - ny * hw),
            (sx - nx * hw, sy - ny * hw),
        ]
        msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": "EST-FUND"})

        # Dimension label
        mid_x = (sx + ex) / 2
        mid_y = (sy + ey) / 2
        msp.add_text(
            f"B={foundation.width_m:.2f}m H={foundation.height_m:.2f}m",
            height=0.05,
            dxfattribs={"layer": "EST-TEXTO"},
        ).set_placement((mid_x + nx * (hw + 0.1), mid_y + ny * (hw + 0.1)))


def _draw_title(msp, project: MasonryProject) -> None:
    """Desenha selo/titulo no canto inferior direito."""
    if not project.floor_plans:
        return

    floor = project.floor_plans[0]
    x = floor.width_m + 1.0
    y = -1.0

    lines = [
        "ESTRUTURA.AI -- Projeto Estrutural",
        f"Alvenaria Estrutural -- Blocos {project.input.block_size.value}cm",
        f"fbk = {project.block_fbk_mpa:.1f} MPa",
        f"Area: {floor.width_m:.2f} x {floor.depth_m:.2f}m = {floor.width_m * floor.depth_m:.1f}m\u00b2",
        f"Pavimentos: {project.input.floors}",
    ]

    for i, line in enumerate(lines):
        msp.add_text(
            line,
            height=0.08,
            dxfattribs={"layer": "EST-TEXTO"},
        ).set_placement((x, y - i * 0.15))


def _find_wall(walls: List[Wall], wall_id: str):
    """Busca parede por ID."""
    for w in walls:
        if w.id == wall_id:
            return w
    return None
