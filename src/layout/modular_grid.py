"""Utilitários de grid modular para alvenaria estrutural.

Todo módulo, parede e dimensão deve ser múltiplo do módulo do bloco:
- Bloco 14cm → módulo 15cm (14cm bloco + 1cm junta)
- Bloco 19cm → módulo 20cm (19cm bloco + 1cm junta)

Referência: NBR 15961-1:2011 — Coordenação modular
"""

import math
from typing import List, Tuple


def get_module(block_size: str) -> float:
    """Retorna o módulo em metros para o tamanho de bloco."""
    return 0.15 if block_size == "14" else 0.20


def snap_to_module(value: float, module: float) -> float:
    """Arredonda um valor para o múltiplo mais próximo do módulo.

    Ex: snap_to_module(3.47, 0.15) → 3.45
        snap_to_module(3.47, 0.20) → 3.40
    """
    return round(round(value / module) * module, 4)


def snap_up_to_module(value: float, module: float) -> float:
    """Arredonda para cima para o próximo múltiplo do módulo."""
    return math.ceil(value / module) * module


def snap_down_to_module(value: float, module: float) -> float:
    """Arredonda para baixo para o múltiplo anterior do módulo."""
    return math.floor(value / module) * module


def generate_grid(width: float, depth: float, module: float) -> Tuple[List[float], List[float]]:
    """Gera linhas de grid modular para a planta.

    Args:
        width: Largura total da edificação (m)
        depth: Profundidade total da edificação (m)
        module: Módulo do bloco (0.15 ou 0.20 m)

    Returns:
        (x_lines, y_lines) — listas de coordenadas das linhas do grid
    """
    snapped_width = snap_to_module(width, module)
    snapped_depth = snap_to_module(depth, module)

    cols = int(round(snapped_width / module)) + 1
    rows = int(round(snapped_depth / module)) + 1

    x_lines = [i * module for i in range(cols)]
    y_lines = [i * module for i in range(rows)]

    return x_lines, y_lines


def validate_modular_coordination(
    walls: list,
    module: float,
    tolerance: float = 0.005,
) -> List[str]:
    """Verifica se todas as paredes estão no grid modular.

    Args:
        walls: Lista de Wall objects (com start, end tuples)
        module: Módulo do bloco (m)
        tolerance: Tolerância em metros (5mm padrão)

    Returns:
        Lista de violações encontradas (vazia = tudo OK)
    """
    violations = []

    for wall in walls:
        wall_id = getattr(wall, 'id', '?')
        for label, point in [("início", wall.start), ("fim", wall.end)]:
            for axis, coord in [("X", point[0]), ("Y", point[1])]:
                remainder = coord % module
                if remainder > tolerance and (module - remainder) > tolerance:
                    snapped = snap_to_module(coord, module)
                    violations.append(
                        f"Parede {wall_id} {label} {axis}={coord:.3f}m "
                        f"fora do módulo {module*100:.0f}cm "
                        f"(mais próximo: {snapped:.3f}m)"
                    )

    return violations


def wall_length_in_modules(length_m: float, module: float) -> int:
    """Retorna o comprimento da parede em módulos inteiros."""
    return int(round(length_m / module))


def blocks_in_wall(length_m: float, height_m: float, block_dims: tuple) -> dict:
    """Calcula a quantidade de blocos para uma parede.

    Args:
        length_m: Comprimento da parede (m)
        height_m: Altura da parede (m)
        block_dims: (largura, altura, comprimento) do bloco em metros

    Returns:
        Dict com quantidade de blocos inteiros e meios-blocos por fiada
    """
    block_w, block_h, block_l = block_dims
    junta = 0.01  # 10mm

    # Módulo horizontal: block_l + junta
    modulo_h = block_l + junta  # 0.40m para bloco 39cm

    # Módulo vertical: block_h + junta
    modulo_v = block_h + junta  # 0.20m para bloco 19cm

    # Blocos por fiada
    blocos_por_fiada = int(length_m / modulo_h)
    resto_h = length_m - blocos_por_fiada * modulo_h

    # Meios-blocos necessários (1 por fiada ímpar para amarração)
    meio_blocos_por_fiada = 1 if resto_h > 0.01 else 0

    # Número de fiadas
    n_fiadas = int(height_m / modulo_v)

    # Total
    blocos_inteiros = blocos_por_fiada * n_fiadas
    meios_blocos = meio_blocos_por_fiada * (n_fiadas // 2)  # amarração alterna

    return {
        "blocos_inteiros": blocos_inteiros,
        "meios_blocos": meios_blocos,
        "fiadas": n_fiadas,
        "blocos_por_fiada": blocos_por_fiada,
    }
