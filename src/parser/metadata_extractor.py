"""Extração de metadados de layers e entidades DXF."""

import re
from typing import Optional
from src.utils.constants import ESPESSURA_DEFAULT


def extract_thickness_from_layer(layer_name: str) -> float:
    """
    Extrai espessura do nome do layer.

    Padrões suportados:
    - LAJE_12CM → 0.12m
    - LAJE_12cm → 0.12m
    - SLAB_120MM → 0.12m
    - LAJE_0.12 → 0.12m
    - LAJE12 → 0.12m

    Retorna espessura padrão se não encontrar.
    """
    upper = layer_name.upper()

    # Padrão: _XXcm ou _XXCM
    match = re.search(r"_?(\d+)\s*CM", upper)
    if match:
        return int(match.group(1)) / 100.0

    # Padrão: _XXXmm ou _XXXMM
    match = re.search(r"_?(\d+)\s*MM", upper)
    if match:
        return int(match.group(1)) / 1000.0

    # Padrão: _0.XX (metros direto)
    match = re.search(r"_?(0\.\d+)", layer_name)
    if match:
        return float(match.group(1))

    # Padrão: LAJE + número (assume cm)
    match = re.search(r"(?:LAJE|SLAB)\s*_?\s*(\d+)", upper)
    if match:
        value = int(match.group(1))
        if value < 10:
            return value / 10.0  # ex: LAJE5 → 0.5m (improvável)
        elif value < 100:
            return value / 100.0  # ex: LAJE12 → 0.12m
        else:
            return value / 1000.0  # ex: LAJE120 → 0.12m

    return ESPESSURA_DEFAULT


def extract_level_from_layer(layer_name: str) -> float:
    """
    Extrai nível/cota do nome do layer.

    Padrões: NIVEL_2.80, N+2.80, COTA_280
    Retorna 0.0 se não encontrar.
    """
    upper = layer_name.upper()

    match = re.search(r"(?:NIVEL|COTA|N\+?)\s*_?\s*(\d+\.?\d*)", upper)
    if match:
        value = float(match.group(1))
        if value > 100:
            return value / 100.0  # ex: 280 → 2.80m
        return value

    return 0.0
