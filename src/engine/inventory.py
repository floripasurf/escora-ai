"""Locadora inventory loader (tenant-aware).

Carrega estoque por tenant/locadora. O frontend estrutura.app tem tela de
upload CSV em /inventario; este modulo consome o JSON correspondente em
``data/inventory/{tenant_id}.json``.

Para cada item, alem da quantidade, o sistema pode capturar:
- ``capacity_kn``: capacidade nominal (a 1.5m / abertura minima)
- ``height_max_m``: abertura/altura maxima de trabalho
- ``height_min_m``: abertura minima
- ``capacity_curve``: lista [[height, capacity], ...] para derating Euler

Sem essas informacoes, o engine cai no catalogo central
(data/catalogs/telescopic_shores.json) usando o ID do modelo como chave.
"""

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_INVENTORY_DIR = Path(__file__).parent.parent.parent / "data" / "inventory"


@dataclass
class InventorySpecs:
    """Especificacoes de um item de inventario (manual §13.1 / item §26 nota 5).

    Quando a locadora cadastra capacidade e altura no CSV, o engine respeita
    esses valores em vez de cair no catalogo central. Permite cadastrar
    escoras estendidas (>4.50m) sem precisar atualizar o catalogo central.
    """

    capacity_kn: Optional[float] = None
    height_min_m: Optional[float] = None
    height_max_m: Optional[float] = None
    capacity_curve: Optional[List[Tuple[float, float]]] = None
    notes: str = ""


@dataclass
class InventoryAvailability:
    locadora: str
    updated_at: str
    items: Dict[str, int] = field(default_factory=dict)
    # Especificacoes opcionais por modelo (manual §26 nota 5).
    specs: Dict[str, InventorySpecs] = field(default_factory=dict)
    tenant_id: str = ""

    def has_extended_shore(self, min_height_m: float = 4.50) -> bool:
        """True quando ha pelo menos um modelo com height_max_m > min."""
        for model_id, spec in self.specs.items():
            if spec.height_max_m is None:
                continue
            if spec.height_max_m > min_height_m and self.items.get(model_id, 0) > 0:
                return True
        return False


def _parse_item_payload(model_id: str, payload: Any) -> Tuple[int, InventorySpecs]:
    """Normaliza um item do JSON em (quantidade, specs).

    Aceita 3 formatos:
    1. ``int`` (legado): ``"ESC310": 18663`` -> quantidade somente.
    2. ``{"qty": int}``: ``"ESC310": {"qty": 18663}``.
    3. ``{"qty": int, "capacity_kn": ..., "height_max_m": ..., ...}``:
       formato completo (manual §13.1 / §26 nota 5).
    """
    if isinstance(payload, int):
        return payload, InventorySpecs()
    if not isinstance(payload, dict):
        raise ValueError(
            f"Item de inventario invalido para '{model_id}': "
            f"esperado int ou dict, recebido {type(payload).__name__}"
        )
    qty = int(payload.get("qty", 0))
    curve = payload.get("capacity_curve")
    if curve:
        curve = [(float(h), float(c)) for h, c in curve]
    specs = InventorySpecs(
        capacity_kn=payload.get("capacity_kn"),
        height_min_m=payload.get("height_min_m"),
        height_max_m=payload.get("height_max_m"),
        capacity_curve=curve,
        notes=payload.get("notes", ""),
    )
    return qty, specs


def load_inventory(
    name: str = "orguel_sjc",
    inventory_dir: Optional[Path] = None,
) -> InventoryAvailability:
    """Load an inventory JSON by short name (no .json suffix).

    Args:
        name: identificador da locadora/tenant (default: orguel_sjc).
        inventory_dir: override do diretorio de inventario; util para
            testes com fixtures isoladas.
    """
    base = inventory_dir or DEFAULT_INVENTORY_DIR
    path = base / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Inventory '{name}' not found at {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items: Dict[str, int] = {}
    specs: Dict[str, InventorySpecs] = {}
    for section in ("telescopic_shores", "tower_modules", "distribution_beams"):
        for model_id, payload in (data.get(section) or {}).items():
            qty, sp = _parse_item_payload(model_id, payload)
            items[model_id] = qty
            specs[model_id] = sp

    inv = InventoryAvailability(
        locadora=data.get("locadora", name),
        updated_at=data.get("updated_at", ""),
        items=items,
        specs=specs,
        tenant_id=data.get("tenant_id", name),
    )
    logger.info(f"Inventory loaded: {inv.locadora} (tenant={inv.tenant_id}) — {len(items)} models")
    return inv


def load_inventory_for_tenant(
    tenant_id: str,
    inventory_dir: Optional[Path] = None,
) -> Optional[InventoryAvailability]:
    """Carrega inventario por tenant_id. Retorna None se nao houver.

    Permite que o pipeline opere com ou sem inventario cadastrado. Quando
    ausente, o engine cai no catalogo central.
    """
    try:
        return load_inventory(tenant_id, inventory_dir)
    except FileNotFoundError:
        logger.warning(f"Inventario nao encontrado para tenant '{tenant_id}'")
        return None


# ---------------------------------------------------------------------------
# CSV import (compativel com a tela de Inventario do estrutura.app)
# ---------------------------------------------------------------------------

# Schema CSV minimo: Modelo, Tipo, Quantidade, Capacidade (kN)
# Schema CSV completo: Modelo, Tipo, Quantidade, Capacidade (kN),
#   Altura minima (m), Altura maxima (m), Curva (h1:c1;h2:c2;...)

# Ordem importa: keywords mais especificos PRIMEIRO (torre antes de escora
# porque "torredeescoramento" contem "escora" como substring).
CSV_SECTION_BY_TIPO = [
    ("torredeescoramento", "tower_modules"),
    ("torredecarga", "tower_modules"),
    ("torremetalica", "tower_modules"),
    ("torre", "tower_modules"),
    ("vigadedistribuicao", "distribution_beams"),
    ("vigametalica", "distribution_beams"),
    ("viga", "distribution_beams"),
    ("vm", "distribution_beams"),
    ("escoraestendida", "telescopic_shores"),
    ("escoratelescopica", "telescopic_shores"),
    ("escorametalica", "telescopic_shores"),
    ("escora", "telescopic_shores"),
]


def parse_inventory_csv(
    csv_content: str,
    tenant_id: str,
    locadora: str = "",
    updated_at: str = "",
) -> Dict[str, Any]:
    """Converte o CSV exportado pela UI em payload JSON compativel.

    Cabecalhos aceitos (case-insensitive, sem acento):
        modelo, tipo, quantidade, capacidade_kn, altura_min_m,
        altura_max_m, curva, notes

    Retorna dict pronto para ser gravado em data/inventory/<tenant>.json.
    """
    def _norm(s: str) -> str:
        return s.strip().lower().replace("(kn)", "").replace("(m)", "").replace(
            "á", "a").replace("â", "a").replace("ã", "a").replace(
            "é", "e").replace("ê", "e").replace("í", "i").replace(
            "ó", "o").replace("ô", "o").replace("ú", "u").replace(
            "ç", "c").replace(" ", "").replace("_", "")

    reader = csv.reader(io.StringIO(csv_content.strip()))
    rows = list(reader)
    if not rows:
        raise ValueError("CSV vazio")

    headers = [_norm(h) for h in rows[0]]
    sections: Dict[str, Dict[str, Any]] = {
        "telescopic_shores": {},
        "tower_modules": {},
        "distribution_beams": {},
    }

    def _idx(name: str) -> Optional[int]:
        try:
            return headers.index(name)
        except ValueError:
            return None

    i_modelo = _idx("modelo")
    i_tipo = _idx("tipo")
    i_qty = _idx("quantidade")
    i_cap = _idx("capacidade") or _idx("capacidadekn")
    i_hmin = _idx("alturamin") or _idx("alturaminima") or _idx("alturaminm")
    i_hmax = _idx("alturamax") or _idx("alturamaxima") or _idx("alturamaxm")
    i_curva = _idx("curva")
    i_notes = _idx("notes") or _idx("notas") or _idx("observacoes")

    if i_modelo is None or i_tipo is None or i_qty is None:
        raise ValueError(
            "CSV invalido: colunas obrigatorias 'modelo', 'tipo' e "
            "'quantidade' nao encontradas"
        )

    def _curve(s: str) -> Optional[List[List[float]]]:
        if not s.strip():
            return None
        pairs = []
        for chunk in s.split(";"):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            h, c = chunk.split(":", 1)
            pairs.append([float(h.strip()), float(c.strip())])
        return pairs or None

    for row in rows[1:]:
        if not row or not row[i_modelo].strip():
            continue
        modelo = row[i_modelo].strip()
        tipo_norm = _norm(row[i_tipo])
        section = None
        for keyword, sec in CSV_SECTION_BY_TIPO:
            if keyword in tipo_norm:
                section = sec
                break
        if section is None:
            logger.warning(f"Tipo '{row[i_tipo]}' nao reconhecido para {modelo}; pulando")
            continue
        qty = int(float(row[i_qty]))
        item: Dict[str, Any] = {"qty": qty}
        if i_cap is not None and row[i_cap].strip():
            item["capacity_kn"] = float(row[i_cap])
        if i_hmin is not None and row[i_hmin].strip():
            item["height_min_m"] = float(row[i_hmin])
        if i_hmax is not None and row[i_hmax].strip():
            item["height_max_m"] = float(row[i_hmax])
        if i_curva is not None:
            curve = _curve(row[i_curva])
            if curve:
                item["capacity_curve"] = curve
        if i_notes is not None and row[i_notes].strip():
            item["notes"] = row[i_notes]
        sections[section][modelo] = item

    return {
        "tenant_id": tenant_id,
        "locadora": locadora or tenant_id,
        "updated_at": updated_at,
        **sections,
    }


def in_stock(
    inv: Optional[InventoryAvailability],
    model_id: str,
    aliases: Optional[list[str]] = None,
) -> bool:
    """True when the locadora has at least one unit of model_id (ou aliases).

    Aceita ``aliases`` (e.g. ["ESC310"]) para resolver IDs legados quando o
    catalogo foi renomeado. Manual §13.1 (nomenclatura ESC2000-3100 etc).
    """
    if inv is None:
        return False
    if inv.items.get(model_id, 0) > 0:
        return True
    for alias in aliases or []:
        if inv.items.get(alias, 0) > 0:
            return True
    return False
