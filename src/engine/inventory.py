"""Locadora inventory loader.

Loads a flat {model_id: stock_count} dict from data/inventory/<name>.json so
the engine can prefer items the partner actually has in stock when running
in mode='inventory'. The JSON is human-editable; once Orguel exposes a live
endpoint, swap load_inventory() to fetch it instead.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_INVENTORY_DIR = Path(__file__).parent.parent.parent / "data" / "inventory"


@dataclass
class InventoryAvailability:
    locadora: str
    updated_at: str
    items: Dict[str, int] = field(default_factory=dict)


def load_inventory(name: str = "orguel_sjc") -> InventoryAvailability:
    """Load an inventory JSON by short name (no .json suffix)."""
    path = DEFAULT_INVENTORY_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Inventory '{name}' not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items: Dict[str, int] = {}
    for section in ("telescopic_shores", "tower_modules", "distribution_beams"):
        for model_id, count in (data.get(section) or {}).items():
            items[model_id] = int(count)

    inv = InventoryAvailability(
        locadora=data.get("locadora", name),
        updated_at=data.get("updated_at", ""),
        items=items,
    )
    logger.info(f"Inventory loaded: {inv.locadora} — {len(items)} models")
    return inv


def in_stock(inv: Optional[InventoryAvailability], model_id: str) -> bool:
    """True when the locadora has at least one unit of model_id."""
    if inv is None:
        return False
    return inv.items.get(model_id, 0) > 0
