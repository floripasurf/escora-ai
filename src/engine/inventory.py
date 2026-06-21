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
import os
import re
import threading
import zipfile
from datetime import date
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

DEFAULT_INVENTORY_DIR = Path(__file__).parent.parent.parent / "data" / "inventory"
_SAFE_INVENTORY_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
_inventory_write_lock = threading.Lock()


def resolve_inventory_dir(inventory_dir: Optional[Path] = None) -> Path:
    """Resolve the inventory directory.

    Production uses the persistent ESCORA_DATA_DIR volume when configured.
    Local development keeps the historical repo path (data/inventory).
    """
    if inventory_dir is not None:
        return Path(inventory_dir)
    override = os.environ.get("ESCORA_INVENTORY_DIR")
    if override:
        return Path(override)
    data_root = os.environ.get("ESCORA_DATA_DIR")
    if data_root:
        return Path(data_root) / "inventory"
    return DEFAULT_INVENTORY_DIR


def inventory_path(name: str, inventory_dir: Optional[Path] = None) -> Path:
    if not name or not _SAFE_INVENTORY_NAME.match(name):
        raise ValueError(f"Nome de inventario invalido: {name!r}")
    return resolve_inventory_dir(inventory_dir) / f"{name}.json"


def _fallback_inventory_path(name: str) -> Path:
    return DEFAULT_INVENTORY_DIR / f"{name}.json"


def _read_inventory_payload(
    name: str,
    path: Path,
    inventory_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    source = path
    if not source.exists() and inventory_dir is None:
        fallback = _fallback_inventory_path(name)
        if fallback.exists() and fallback != source:
            source = fallback
    if not source.exists():
        return {}
    with open(source, "r", encoding="utf-8") as f:
        return json.load(f)


def _prepare_inventory_payload(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload)
    data["tenant_id"] = data.get("tenant_id") or name
    data["updated_at"] = date.today().isoformat()
    for section in ("telescopic_shores", "tower_modules", "distribution_beams", "accessories"):
        data.setdefault(section, {})
    return data


def _write_inventory_payload(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp_path = path.with_name(f".{path.stem}.{os.getpid()}.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


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
    path = inventory_path(name, inventory_dir)
    if not path.exists() and inventory_dir is None:
        fallback = _fallback_inventory_path(name)
        if fallback.exists() and fallback != path:
            path = fallback
    if not path.exists():
        raise FileNotFoundError(f"Inventory '{name}' not found at {path}")

    data = _read_inventory_payload(name, path, inventory_dir)

    items: Dict[str, int] = {}
    specs: Dict[str, InventorySpecs] = {}
    for section in ("telescopic_shores", "tower_modules", "distribution_beams", "accessories"):
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


def update_inventory(
    name: str,
    updater: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
    inventory_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Read, mutate and persist an inventory while holding the file lock."""
    path = inventory_path(name, inventory_dir)
    lock_path = path.with_suffix(path.suffix + ".lock")

    with _inventory_write_lock:
        import fcntl

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                data = _read_inventory_payload(name, path, inventory_dir)
                updated = updater(data)
                if updated is not None:
                    data = updated
                data = _prepare_inventory_payload(name, data)
                _write_inventory_payload(path, data)
                return data
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def save_inventory(
    name: str,
    payload: Dict[str, Any],
    inventory_dir: Optional[Path] = None,
) -> Path:
    """Persist an inventory JSON with atomic replace semantics."""
    path = inventory_path(name, inventory_dir)
    data = _prepare_inventory_payload(name, payload)
    lock_path = path.with_suffix(path.suffix + ".lock")

    with _inventory_write_lock:
        import fcntl

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                _write_inventory_payload(path, data)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    return path


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
    ("acessorio", "accessories"),
    ("acessorios", "accessories"),
    ("cruzeta", "accessories"),
    ("forcado", "accessories"),
    ("sapata", "accessories"),
    ("diagonal", "accessories"),
    ("tripe", "accessories"),
    ("torredeescoramento", "tower_modules"),
    ("torredecarga", "tower_modules"),
    ("torremetalica", "tower_modules"),
    ("torre", "tower_modules"),
    ("barrote", "distribution_beams"),
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
    Marcadores como N/A, N/D e "-" sao tratados como campo nao preenchido.

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
        "accessories": {},
    }

    def _idx(name: str) -> Optional[int]:
        try:
            return headers.index(name)
        except ValueError:
            return None

    def _is_empty_marker(value: str) -> bool:
        marker = _norm(value).replace("/", "").replace("-", "").replace(".", "")
        return marker in {"", "na", "nd", "naoaplicavel", "naoseaplica"}

    def _cell(row: list[str], index: Optional[int]) -> str:
        if index is None or index >= len(row):
            return ""
        value = row[index].strip()
        return "" if _is_empty_marker(value) else value

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
        if not s.strip() or _is_empty_marker(s):
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
        if not row or not _cell(row, i_modelo):
            continue
        modelo = _cell(row, i_modelo)
        tipo_raw = _cell(row, i_tipo)
        tipo_norm = _norm(tipo_raw)
        section = None
        for keyword, sec in CSV_SECTION_BY_TIPO:
            if keyword in tipo_norm:
                section = sec
                break
        if section is None:
            logger.warning(f"Tipo '{tipo_raw}' nao reconhecido para {modelo}; pulando")
            continue
        qty = int(float(_cell(row, i_qty)))
        item: Dict[str, Any] = {"qty": qty}
        cap = _cell(row, i_cap)
        if cap:
            item["capacity_kn"] = float(cap)
        hmin = _cell(row, i_hmin)
        if hmin:
            item["height_min_m"] = float(hmin)
        hmax = _cell(row, i_hmax)
        if hmax:
            item["height_max_m"] = float(hmax)
        if i_curva is not None:
            curve = _curve(_cell(row, i_curva))
            if curve:
                item["capacity_curve"] = curve
        notes = _cell(row, i_notes)
        if notes:
            item["notes"] = notes
        sections[section][modelo] = item

    return {
        "tenant_id": tenant_id,
        "locadora": locadora or tenant_id,
        "updated_at": updated_at,
        **sections,
    }


def parse_inventory_xlsx(
    xlsx_content: bytes,
    tenant_id: str,
    locadora: str = "",
    updated_at: str = "",
) -> Dict[str, Any]:
    """Converte a primeira aba de um XLSX em payload JSON de inventario."""

    def _col_index(cell_ref: str) -> int:
        letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
        idx = 0
        for ch in letters:
            idx = idx * 26 + (ord(ch) - ord("A") + 1)
        return idx - 1

    def _text(el: ET.Element, ns: dict[str, str]) -> str:
        if el.get("t") == "inlineStr":
            parts = [t.text or "" for t in el.findall(".//main:t", ns)]
            return "".join(parts)
        v = el.find("main:v", ns)
        return v.text if v is not None and v.text is not None else ""

    with zipfile.ZipFile(io.BytesIO(xlsx_content)) as zf:
        names = set(zf.namelist())
        if "xl/worksheets/sheet1.xml" not in names:
            raise ValueError("XLSX invalido: primeira aba nao encontrada")

        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("main:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//main:t", ns)))

        root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        for row_el in root.findall(".//main:sheetData/main:row", ns):
            row_values: list[str] = []
            for c in row_el.findall("main:c", ns):
                idx = _col_index(c.get("r", "A1"))
                while len(row_values) <= idx:
                    row_values.append("")
                value = _text(c, ns)
                if c.get("t") == "s" and value:
                    try:
                        value = shared[int(value)]
                    except (IndexError, ValueError):
                        value = ""
                row_values[idx] = value
            rows.append(row_values)

    csv_buf = io.StringIO()
    writer = csv.writer(csv_buf)
    writer.writerows(rows)
    return parse_inventory_csv(
        csv_buf.getvalue(),
        tenant_id=tenant_id,
        locadora=locadora,
        updated_at=updated_at,
    )


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
