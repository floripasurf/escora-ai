"""Seleção de modelo de escora do catálogo."""

import json
from pathlib import Path
from typing import List, Optional
from src.models.shore import ShoreCatalogEntry


def load_catalog(catalog_path: Optional[str] = None) -> List[ShoreCatalogEntry]:
    """Carrega catálogo de escoras de um arquivo JSON."""
    if catalog_path is None:
        catalog_path = str(
            Path(__file__).parent.parent.parent / "data" / "catalogs" / "telescopic_shores.json"
        )

    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [ShoreCatalogEntry(**entry) for entry in data["shores"]]


def select_shore(
    catalog: List[ShoreCatalogEntry],
    required_height_m: float,
    required_capacity_kn: float,
) -> Optional[ShoreCatalogEntry]:
    """
    Seleciona a escora mais adequada do catálogo.

    Critérios:
    1. Altura compatível (required_height dentro do range)
    2. Capacidade de carga suficiente
    3. Menor capacidade que atenda (mais econômica)
    """
    compatible = [
        shore for shore in catalog
        if shore.height_min_m <= required_height_m <= shore.height_max_m
        and shore.load_capacity_kn >= required_capacity_kn
    ]

    if not compatible:
        # Tenta sem filtro de altura (pode usar extensão)
        compatible = [
            shore for shore in catalog
            if shore.load_capacity_kn >= required_capacity_kn
        ]

    if not compatible:
        return None

    # Retorna a mais econômica (menor capacidade que atenda)
    return min(compatible, key=lambda s: s.load_capacity_kn)
