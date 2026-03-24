"""Validação dos resultados de escoramento."""

from typing import List, Tuple
from src.models.shore import PositionedShore
from src.utils.constants import ESPACAMENTO_MAX_DEFAULT


def validate_shore_capacity(shores: List[PositionedShore]) -> List[str]:
    """Verifica se nenhuma escora excede sua capacidade."""
    errors = []
    for i, shore in enumerate(shores):
        if shore.utilization_ratio > 1.0:
            errors.append(
                f"Escora #{i+1} em ({shore.x:.2f}, {shore.y:.2f}): "
                f"utilização {shore.utilization_ratio:.1%} > 100% "
                f"(carga {shore.load_applied_kn:.1f} kN > "
                f"capacidade {shore.shore.load_capacity_kn:.1f} kN)"
            )
    return errors


def validate_spacing(
    spacing_x: float,
    spacing_y: float,
    max_spacing: float = ESPACAMENTO_MAX_DEFAULT,
) -> List[str]:
    """Verifica se o espaçamento está dentro do limite."""
    errors = []
    if spacing_x > max_spacing:
        errors.append(
            f"Espaçamento X ({spacing_x:.2f}m) excede máximo ({max_spacing:.2f}m)"
        )
    if spacing_y > max_spacing:
        errors.append(
            f"Espaçamento Y ({spacing_y:.2f}m) excede máximo ({max_spacing:.2f}m)"
        )
    return errors


def validate_result(
    shores: List[PositionedShore],
    spacing_x: float,
    spacing_y: float,
    max_spacing: float = ESPACAMENTO_MAX_DEFAULT,
) -> Tuple[bool, List[str]]:
    """
    Validação completa do resultado.
    Retorna (is_valid, list_of_errors).
    """
    errors = []
    errors.extend(validate_shore_capacity(shores))
    errors.extend(validate_spacing(spacing_x, spacing_y, max_spacing))

    if not shores:
        errors.append("Nenhuma escora posicionada")

    return len(errors) == 0, errors
