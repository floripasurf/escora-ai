"""Seleção de modelo de escora do catálogo."""

import json
import logging
from pathlib import Path
from typing import List, Literal, Optional
from src.models.shore import ShoreCatalogEntry
from src.engine.inventory import InventoryAvailability, in_stock

logger = logging.getLogger(__name__)


def load_catalog(catalog_path: Optional[str] = None) -> List[ShoreCatalogEntry]:
    """Carrega catálogo de escoras de um arquivo JSON."""
    if catalog_path is None:
        catalog_path = str(
            Path(__file__).parent.parent.parent / "data" / "catalogs" / "telescopic_shores.json"
        )

    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [ShoreCatalogEntry(**entry) for entry in data["shores"]]


def _is_selectable(shore: ShoreCatalogEntry) -> bool:
    """Retorna True se a escora pode ser selecionada pelo engine.

    Filtros (manual §8 e §13.1):
    - available=False: modelo nao disponivel.
    - enabled=False: placeholder nao configurado (ex: ESC Estendida sem curve).
    - for_sale_only=True: modelo de venda, nao deve ser default em locacao.
    - not_standard_rental=True: nao usar como padrao sem confirmar estoque.
    """
    if not shore.available or not shore.enabled:
        return False
    if shore.for_sale_only or shore.not_standard_rental:
        return False
    return True


def select_shore(
    catalog: List[ShoreCatalogEntry],
    required_height_m: float,
    required_capacity_kn: float,
    mode: Literal["price", "inventory"] = "price",
    inventory: Optional[InventoryAvailability] = None,
) -> Optional[ShoreCatalogEntry]:
    """Seleciona a escora mais adequada do catálogo.

    mode='price' (default): minimiza capacidade derateada (mais econômica).
    mode='inventory': prefere modelos em estoque na locadora informada,
        caindo de volta para 'price' se nada em estoque atende.

    Filtra modelos nao-selecionaveis (ESC Junior somente-venda, placeholders
    nao configurados, etc) via `_is_selectable`. Manual §13.1.
    """
    selectable = [s for s in catalog if _is_selectable(s)]
    compatible = [
        shore for shore in selectable
        if shore.height_min_m <= required_height_m <= shore.height_max_m
        and shore.effective_capacity(required_height_m) >= required_capacity_kn
    ]

    if not compatible:
        compatible = [
            shore for shore in selectable
            if shore.effective_capacity(required_height_m) >= required_capacity_kn
        ]

    if not compatible:
        return None

    if mode == "inventory" and inventory is not None:
        in_stock_items = [s for s in compatible if in_stock(inventory, s.id)]
        if in_stock_items:
            return min(
                in_stock_items,
                key=lambda s: s.effective_capacity(required_height_m),
            )
        chosen = min(
            compatible, key=lambda s: s.effective_capacity(required_height_m),
        )
        logger.warning(f"Sem estoque {inventory.locadora}: usando {chosen.id}")
        return chosen

    return min(compatible, key=lambda s: s.effective_capacity(required_height_m))
