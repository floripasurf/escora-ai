"""Branch-scoped inventory persistence for the self-service API."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from xml.sax.saxutils import escape
import zipfile

from src.auth.branches import Branch
from src.engine.inventory import (
    DEFAULT_INVENTORY_DIR,
    inventory_path,
    parse_inventory_csv,
    parse_inventory_xlsx,
    save_inventory,
    update_inventory,
)

SECTIONS = ("telescopic_shores", "tower_modules", "distribution_beams", "accessories")

SECTION_LABELS = {
    "telescopic_shores": "Escora metalica",
    "tower_modules": "Torre de escoramento",
    "distribution_beams": "Viga de distribuicao",
    "accessories": "Acessorio",
}

TEMPLATE_HEADERS = [
    "Modelo",
    "Tipo",
    "Quantidade",
    "Capacidade (kN)",
    "Altura minima (m)",
    "Altura maxima (m)",
    "Momento adm (kN.m)",
    "Vao max (m)",
    "Curva",
    "Observacoes",
]

LOW_STOCK_THRESHOLD = 200


@dataclass
class InventoryItemInput:
    section: str
    qty: int
    capacity_kn: Optional[float] = None
    height_min_m: Optional[float] = None
    height_max_m: Optional[float] = None
    capacity_curve: Optional[list[list[float]]] = None
    notes: str = ""


def _raw_inventory_path(name: str) -> Path:
    return inventory_path(name)


def _read_payload(branch: Branch) -> Dict[str, Any]:
    path = _raw_inventory_path(branch.inventory_name)
    source = path
    if not source.exists():
        fallback = DEFAULT_INVENTORY_DIR / f"{branch.inventory_name}.json"
        if fallback.exists() and fallback != source:
            source = fallback
    if source.exists():
        data = json.loads(source.read_text(encoding="utf-8"))
    else:
        data = {}
    return _normalize_payload(data, branch)


def _normalize_payload(data: Dict[str, Any], branch: Branch) -> Dict[str, Any]:
    payload = dict(data or {})
    payload["tenant_id"] = payload.get("tenant_id") or branch.inventory_name
    payload["locadora"] = payload.get("locadora") or branch.display_name or branch.inventory_name
    payload["updated_at"] = payload.get("updated_at") or ""
    for section in SECTIONS:
        value = payload.get(section)
        payload[section] = value if isinstance(value, dict) else {}
    return payload


def _item_payload_to_dict(section: str, model_id: str, payload: Any) -> Dict[str, Any]:
    if isinstance(payload, int):
        qty = payload
        raw: Dict[str, Any] = {}
    elif isinstance(payload, dict):
        qty = int(payload.get("qty", 0))
        raw = payload
    else:
        qty = 0
        raw = {}

    if qty <= 0:
        status = "out"
        status_label = "Sem estoque"
    elif qty <= LOW_STOCK_THRESHOLD:
        status = "low"
        status_label = "Estoque baixo"
    else:
        status = "ok"
        status_label = "Disponivel"

    return {
        "model_id": model_id,
        "section": section,
        "type": SECTION_LABELS[section],
        "qty": qty,
        "capacity_kn": raw.get("capacity_kn"),
        "height_min_m": raw.get("height_min_m"),
        "height_max_m": raw.get("height_max_m"),
        "capacity_curve": raw.get("capacity_curve"),
        "notes": raw.get("notes", ""),
        "status": status,
        "status_label": status_label,
    }


def _iter_items(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for section in SECTIONS:
        for model_id, item_payload in sorted(payload.get(section, {}).items()):
            yield _item_payload_to_dict(section, model_id, item_payload)


def inventory_summary(branch: Branch) -> Dict[str, Any]:
    payload = _read_payload(branch)
    return _summary_from_payload(branch, payload)


def _summary_from_payload(branch: Branch, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "inventory_name": branch.inventory_name,
        "locadora": payload.get("locadora", ""),
        "updated_at": payload.get("updated_at", ""),
        "sections": [
            {"id": section, "label": SECTION_LABELS[section]}
            for section in SECTIONS
        ],
        "items": list(_iter_items(payload)),
    }


def _find_existing_section(payload: Dict[str, Any], model_id: str) -> Optional[str]:
    for section in SECTIONS:
        if model_id in payload.get(section, {}):
            return section
    return None


def _serialize_item(item: InventoryItemInput) -> Dict[str, Any]:
    out: Dict[str, Any] = {"qty": int(item.qty)}
    optional = {
        "capacity_kn": item.capacity_kn,
        "height_min_m": item.height_min_m,
        "height_max_m": item.height_max_m,
        "capacity_curve": item.capacity_curve,
        "notes": item.notes.strip() if item.notes else "",
    }
    for key, value in optional.items():
        if value not in (None, ""):
            out[key] = value
    return out


def _validated_stored_item(model_id: str, payload: Any) -> Any:
    if isinstance(payload, int):
        if payload < 0:
            raise ValueError(f"Quantidade nao pode ser negativa para {model_id}")
        return payload
    if not isinstance(payload, dict):
        raise ValueError(f"Item invalido para {model_id}: esperado numero ou objeto")

    qty = payload.get("qty")
    if qty is None:
        raise ValueError(f"Quantidade obrigatoria para {model_id}")
    try:
        qty_int = int(qty)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Quantidade invalida para {model_id}") from e
    if qty_int < 0:
        raise ValueError(f"Quantidade nao pode ser negativa para {model_id}")

    out: Dict[str, Any] = {"qty": qty_int}
    for field in ("capacity_kn", "height_min_m", "height_max_m"):
        value = payload.get(field)
        if value in (None, ""):
            continue
        try:
            num = float(value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"{field} invalido para {model_id}") from e
        if num < 0:
            raise ValueError(f"{field} nao pode ser negativo para {model_id}")
        out[field] = num

    if (
        out.get("height_min_m") is not None
        and out.get("height_max_m") is not None
        and out["height_min_m"] > out["height_max_m"]
    ):
        raise ValueError(f"Altura minima maior que maxima para {model_id}")

    curve = payload.get("capacity_curve")
    if curve not in (None, ""):
        if not isinstance(curve, list):
            raise ValueError(f"Curva de capacidade invalida para {model_id}")
        parsed_curve = []
        for pair in curve:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f"Curva de capacidade deve usar pares para {model_id}")
            parsed_curve.append([float(pair[0]), float(pair[1])])
        out["capacity_curve"] = parsed_curve

    notes = payload.get("notes")
    if notes not in (None, ""):
        out["notes"] = str(notes)
    return out


def _validated_inventory_payload(
    payload: Dict[str, Any],
    branch: Branch,
) -> Dict[str, Any]:
    data = _normalize_payload(payload, branch)
    for section in SECTIONS:
        validated: Dict[str, Any] = {}
        for raw_model_id, item_payload in data[section].items():
            model_id = str(raw_model_id).strip()
            if not model_id:
                raise ValueError("Modelo vazio no inventario")
            validated[model_id] = _validated_stored_item(model_id, item_payload)
        data[section] = validated
    return data


def upsert_inventory_item(
    branch: Branch,
    model_id: str,
    item: InventoryItemInput,
) -> Dict[str, Any]:
    model_id = model_id.strip()
    if not model_id:
        raise ValueError("Modelo e obrigatorio")
    if item.section not in SECTIONS:
        raise ValueError("Tipo de item invalido")
    if item.qty < 0:
        raise ValueError("Quantidade nao pode ser negativa")

    def _mutate(raw: Dict[str, Any]) -> Dict[str, Any]:
        payload = _normalize_payload(raw, branch)
        existing = _find_existing_section(payload, model_id)
        if existing and existing != item.section:
            payload[existing].pop(model_id, None)
        payload[item.section][model_id] = _serialize_item(item)
        return payload

    payload = update_inventory(branch.inventory_name, _mutate)
    return _summary_from_payload(branch, _normalize_payload(payload, branch))


def delete_inventory_item(branch: Branch, model_id: str) -> Dict[str, Any]:
    def _mutate(raw: Dict[str, Any]) -> Dict[str, Any]:
        payload = _normalize_payload(raw, branch)
        section = _find_existing_section(payload, model_id)
        if section is None:
            raise KeyError(model_id)
        payload[section].pop(model_id, None)
        return payload

    payload = update_inventory(branch.inventory_name, _mutate)
    return _summary_from_payload(branch, _normalize_payload(payload, branch))


def replace_inventory(branch: Branch, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = _validated_inventory_payload(payload, branch)
    save_inventory(branch.inventory_name, data)
    return inventory_summary(branch)


def import_inventory_csv(branch: Branch, csv_text: str) -> Dict[str, Any]:
    payload = parse_inventory_csv(
        csv_text,
        tenant_id=branch.inventory_name,
        locadora=branch.display_name or branch.inventory_name,
    )
    save_inventory(branch.inventory_name, payload)
    return inventory_summary(branch)


def import_inventory_xlsx(branch: Branch, content: bytes) -> Dict[str, Any]:
    payload = parse_inventory_xlsx(
        content,
        tenant_id=branch.inventory_name,
        locadora=branch.display_name or branch.inventory_name,
    )
    save_inventory(branch.inventory_name, payload)
    return inventory_summary(branch)


def _catalog_root() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "catalogs"


def _curve_text(curve: Any) -> str:
    if not curve:
        return ""
    return ";".join(f"{float(h):g}:{float(c):g}" for h, c in curve)


def template_rows() -> list[list[Any]]:
    rows: list[list[Any]] = []
    seen: set[str] = set()

    def add(
        model_id: str,
        tipo: str,
        capacity: Any = "",
        h_min: Any = "",
        h_max: Any = "",
        moment: Any = "",
        span: Any = "",
        curve: Any = "",
        notes: str = "",
    ) -> None:
        model_id = str(model_id).strip()
        if not model_id or model_id in seen:
            return
        seen.add(model_id)

        def _num(value: Any) -> Any:
            return value if value not in (None, "", 0.0) else ""

        rows.append([
            model_id,
            tipo,
            0,
            _num(capacity),
            h_min if h_min is not None else "",
            h_max if h_max is not None else "",
            _num(moment),
            _num(span),
            _curve_text(curve),
            (notes or "").strip(),
        ])

    shores_path = _catalog_root() / "telescopic_shores.json"
    if shores_path.exists():
        data = json.loads(shores_path.read_text(encoding="utf-8"))
        for shore in data.get("shores", []):
            aliases = shore.get("aliases") or []
            notes = shore.get("notes", "")
            if aliases:
                notes = f"Aliases aceitos: {', '.join(aliases)}. {notes}".strip()
            add(
                shore.get("id", ""),
                "Escora metalica",
                capacity=shore.get("load_capacity_kn"),
                h_min=shore.get("height_min_m"),
                h_max=shore.get("height_max_m"),
                curve=shore.get("capacity_curve"),
                notes=notes,
            )
            for alias in aliases:
                add(
                    alias,
                    "Escora metalica",
                    capacity=shore.get("load_capacity_kn"),
                    h_min=shore.get("height_min_m"),
                    h_max=shore.get("height_max_m"),
                    curve=shore.get("capacity_curve"),
                    notes=f"Alias legado de {shore.get('id', '')}",
                )

    towers_path = _catalog_root() / "shoring_towers.json"
    if towers_path.exists():
        data = json.loads(towers_path.read_text(encoding="utf-8"))
        for tower in data.get("towers", []):
            add(
                tower.get("id", ""),
                "Torre de escoramento",
                capacity=tower.get("load_capacity_kn"),
                h_max=tower.get("max_height_m"),
                curve=tower.get("capacity_curve"),
                notes=tower.get("notes", ""),
            )
        for beam in data.get("distribution_beams", []):
            model = str(beam.get("model", ""))
            tipo = "Barrote / viga de distribuicao" if model.startswith("VM80") else "Viga de distribuicao"
            add(
                beam.get("id", ""),
                tipo,
                moment=beam.get("moment_capacity_knm"),
                span=beam.get("max_span_m"),
                notes=beam.get("notes", ""),
            )
        for accessory in data.get("accessories", []):
            add(
                accessory.get("id", ""),
                "Acessorio",
                notes=accessory.get("notes", ""),
            )

    return rows


def template_csv() -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerows(template_rows())
    return buf.getvalue()


def _xlsx_cell(value: Any, row: int, col: int, style: int = 0) -> str:
    col_name = ""
    n = col + 1
    while n:
        n, rem = divmod(n - 1, 26)
        col_name = chr(65 + rem) + col_name
    ref = f"{col_name}{row}"
    style_attr = f' s="{style}"' if style else ""
    if value is None or value == "":
        return f'<c r="{ref}"{style_attr}/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t>{escape(str(value))}</t></is></c>'


def template_xlsx() -> bytes:
    rows = [TEMPLATE_HEADERS, *template_rows()]
    sheet_rows = []
    for r_idx, row in enumerate(rows, start=1):
        style = 1 if r_idx == 1 else 0
        cells = "".join(_xlsx_cell(value, r_idx, c_idx, style) for c_idx, value in enumerate(row))
        sheet_rows.append(f'<row r="{r_idx}">{cells}</row>')

    max_row = len(rows)
    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <cols>
    <col min="1" max="1" width="22" customWidth="1"/>
    <col min="2" max="2" width="30" customWidth="1"/>
    <col min="3" max="3" width="13" customWidth="1"/>
    <col min="4" max="9" width="18" customWidth="1"/>
    <col min="10" max="10" width="80" customWidth="1"/>
  </cols>
  <sheetData>{''.join(sheet_rows)}</sheetData>
  <autoFilter ref="A1:J{max_row}"/>
</worksheet>'''

    files = {
        "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''',
        "xl/workbook.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Inventario" sheetId="1" r:id="rId1"/></sheets>
</workbook>''',
        "xl/_rels/workbook.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>''',
        "xl/styles.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font/><font><b/><color rgb="FFFFFFFF"/></font></fonts>
  <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>''',
        "xl/worksheets/sheet1.xml": sheet_xml,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()
