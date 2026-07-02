"""Calculadora de cargas para alvenaria estrutural.

Calcula cargas verticais acumuladas nas paredes:
  Cobertura → Paredes superiores → Laje entrepiso → Paredes térreo → Fundação

Referências:
- NBR 15961-1:2011 — Alvenaria estrutural — Blocos de concreto — Projeto
- NBR 6120:2019 — Ações para o cálculo de estruturas
- NBR 6118:2023 — Projeto de estruturas de concreto
"""

import logging
from typing import List, Tuple

from src.models.masonry import (
    Wall, WallOpening, Lintel, TieBeam, FloorPlan, ProjectInput,
)
from src.utils.masonry_constants import (
    GAMMA_ALVENARIA, GAMMA_F, BLOCK_STRENGTHS_MPA, WALL_CAPACITY_KN_PER_M,
    PP_COBERTURA_CERAMICA, Q_COBERTURA, Q_RESIDENCIAL,
    PP_REVESTIMENTO, PP_CONTRAPISO, PP_LAJE_POR_CM,
    LAJE_PRE_ESPESSURA, PP_LAJE_PRE,
    VERGA_APOIO_MIN_CM, VERGA_ALTURA_MIN, VERGA_ARMADURA_PADRAO,
    CONTRAVERGA_VAO_MIN,
    CINTA_RESPALDO_ALTURA, CINTA_ARMADURA_MIN,
)

logger = logging.getLogger(__name__)


def calculate_wall_self_weight(wall: Wall) -> float:
    """Peso próprio da parede de alvenaria (kN/m).

    q_pp = γ_alvenaria × t × h

    Returns:
        Carga linear em kN/m (por metro de comprimento de parede)
    """
    return GAMMA_ALVENARIA * wall.thickness_m * wall.height_m


def calculate_slab_load_on_wall(
    wall: Wall,
    slab_thickness_cm: float = LAJE_PRE_ESPESSURA,
    tributary_width_m: float = 2.0,
    use_pre_slab: bool = True,
) -> float:
    """Carga da laje sobre a parede (kN/m).

    Args:
        wall: Parede que recebe a carga
        slab_thickness_cm: Espessura da laje (cm)
        tributary_width_m: Largura de influência (metade do vão da laje)
        use_pre_slab: Se True, usa peso de laje pré-moldada

    Returns:
        Carga linear em kN/m
    """
    if use_pre_slab:
        pp_laje = PP_LAJE_PRE  # kN/m²
    else:
        pp_laje = PP_LAJE_POR_CM * slab_thickness_cm  # kN/m²

    # Peso próprio da laje + revestimento + contrapiso + sobrecarga
    q_total = pp_laje + PP_REVESTIMENTO + PP_CONTRAPISO + Q_RESIDENCIAL

    return q_total * tributary_width_m


def calculate_roof_load(
    tributary_width_m: float = 2.0,
    roof_type: str = "wooden_truss",
) -> float:
    """Carga da cobertura sobre a parede (kN/m).

    Telhado de madeira com telha cerâmica (padrão MCMV).

    Returns:
        Carga linear em kN/m
    """
    pp = PP_COBERTURA_CERAMICA if roof_type != "fibrocimento" else 0.5
    q = pp + Q_COBERTURA
    return q * tributary_width_m


def calculate_total_wall_load(
    wall: Wall,
    is_top_floor: bool = True,
    tributary_width_m: float = 2.0,
    slab_thickness_cm: float = LAJE_PRE_ESPESSURA,
    floors_above: int = 0,
    roof_type: str = "wooden_truss",
) -> float:
    """Carga total acumulada na parede (kN/m) — já majorada.

    Acumula de cima para baixo:
    1. Cobertura (se pavimento superior ou se é o único pavimento)
    2. Peso próprio da parede deste nível
    3. Laje(s) acima (se houver pavimento superior)
    4. Paredes acima (se houver)

    Returns:
        Carga majorada (×γf) em kN/m
    """
    # Peso próprio da parede
    q_pp = calculate_wall_self_weight(wall)

    # Carga da cobertura
    q_roof = calculate_roof_load(tributary_width_m, roof_type)

    # Carga da laje (se não é o topo — tem laje entre pavimentos acima)
    q_slab = 0.0
    if not is_top_floor:
        q_slab = calculate_slab_load_on_wall(
            wall, slab_thickness_cm, tributary_width_m
        )

    # Acumular paredes de pavimentos acima
    q_above = 0.0
    if floors_above > 0:
        # Parede acima + laje entre pisos
        q_above = floors_above * (q_pp + calculate_slab_load_on_wall(
            wall, slab_thickness_cm, tributary_width_m
        ))

    # Total característico
    q_char = q_pp + q_roof + q_slab + q_above

    # Majorado
    q_design = q_char * GAMMA_F

    return q_design


def select_block_strength(
    load_kn_per_m: float,
    thickness_cm: int,
) -> float:
    """Seleciona a resistência mínima do bloco (fbk) para a carga dada.

    Verifica: Nd ≤ Rd = (η × fbk × t × 1m) / γm

    Args:
        load_kn_per_m: Carga de projeto (majorada) por metro de parede (kN/m)
        thickness_cm: Espessura da parede em cm (14 ou 19)

    Returns:
        fbk em MPa — menor resistência que atende
    """
    for fbk in BLOCK_STRENGTHS_MPA:
        capacity = WALL_CAPACITY_KN_PER_M.get((fbk, thickness_cm))
        if capacity is None:
            continue
        if capacity >= load_kn_per_m:
            return fbk

    # Se nenhum bloco atende, retorna o mais forte disponível
    logger.warning(
        f"Nenhum bloco atende Nd={load_kn_per_m:.1f} kN/m "
        f"(t={thickness_cm}cm). Usando fbk máximo."
    )
    return max(BLOCK_STRENGTHS_MPA)


def calculate_lintel(opening: WallOpening, wall_thickness_m: float) -> Lintel:
    """Dimensiona a verga (e contraverga se aplicável) para uma abertura.

    Verga: vão = largura da abertura + 2 × apoio mínimo (30cm)
    Contraverga: obrigatória para vãos > 60cm (janelas)

    Returns:
        Lintel com dimensionamento
    """
    apoio = VERGA_APOIO_MIN_CM / 100.0  # 0.30m
    vao = opening.width_m + 2 * apoio

    return Lintel(
        wall_id="",  # será preenchido pelo chamador
        opening_index=0,
        width_m=wall_thickness_m,
        height_m=VERGA_ALTURA_MIN,
        span_m=vao,
        rebar=VERGA_ARMADURA_PADRAO,
    )


def calculate_tie_beams(floor_plan: FloorPlan) -> List[TieBeam]:
    """Gera cintas de amarração no respaldo de todas as paredes.

    A cinta percorre o topo de todas as paredes estruturais,
    formando um anel contínuo em cada nível.

    Returns:
        Lista de TieBeam
    """
    if not floor_plan.walls:
        return []

    # Collect all wall endpoints to form the tie beam path
    path = []
    thickness = floor_plan.walls[0].thickness_m if floor_plan.walls else 0.14

    for wall in floor_plan.walls:
        if wall.is_structural:
            path.append(wall.start)
            path.append(wall.end)

    # Remove duplicates preserving order
    seen = set()
    unique_path = []
    for p in path:
        key = (round(p[0], 3), round(p[1], 3))
        if key not in seen:
            seen.add(key)
            unique_path.append(p)

    return [TieBeam(
        level="respaldo",
        path=unique_path,
        width_m=thickness,
        height_m=CINTA_RESPALDO_ALTURA,
        rebar=CINTA_ARMADURA_MIN,
    )]


def calculate_lintels(floor_plan: FloorPlan) -> List[Lintel]:
    """Gera vergas e contravergas para todas as aberturas do pavimento."""
    lintels = []

    for wall in floor_plan.walls:
        for i, opening in enumerate(wall.openings):
            lintel = calculate_lintel(opening, wall.thickness_m)
            lintel.wall_id = wall.id
            lintel.opening_index = i
            lintels.append(lintel)

            # Contraverga para janelas com vão > 60cm
            if (opening.type.value == "window" and
                opening.width_m > CONTRAVERGA_VAO_MIN):
                contra = Lintel(
                    wall_id=wall.id,
                    opening_index=i,
                    width_m=wall.thickness_m,
                    height_m=VERGA_ALTURA_MIN,
                    span_m=opening.width_m + 2 * (VERGA_APOIO_MIN_CM / 100.0),
                    rebar=VERGA_ARMADURA_PADRAO,
                )
                lintels.append(contra)

    return lintels


def calculate_masonry_project(
    input: ProjectInput,
    floor_plan: FloorPlan,
) -> Tuple[FloorPlan, float]:
    """Calcula todas as cargas e seleciona o bloco para o projeto.

    Args:
        input: Dados de entrada do projeto
        floor_plan: Planta já gerada pelo solver

    Returns:
        (floor_plan atualizado, fbk_selecionado)
    """
    thickness_cm = int(input.block_size.value)
    max_load = 0.0

    # Average tributary width (half the average room span)
    # Estimate from building dimensions
    avg_tributary = min(floor_plan.width_m, floor_plan.depth_m) / 4.0

    for wall in floor_plan.walls:
        if not wall.is_structural:
            continue

        load = calculate_total_wall_load(
            wall=wall,
            is_top_floor=(input.floors == 1),
            tributary_width_m=avg_tributary,
            floors_above=max(0, input.floors - 1),
            roof_type=input.roof_type,
        )
        wall.load_kn_per_m = load
        max_load = max(max_load, load)

    # Select block strength based on the most loaded wall
    fbk = select_block_strength(max_load, thickness_cm)

    # Calculate lintels
    floor_plan.lintels = calculate_lintels(floor_plan)

    # Calculate tie beams
    floor_plan.tie_beams = calculate_tie_beams(floor_plan)

    logger.info(
        f"Cargas calculadas: max={max_load:.1f} kN/m, "
        f"bloco selecionado: fbk={fbk:.1f} MPa"
    )

    return floor_plan, fbk
