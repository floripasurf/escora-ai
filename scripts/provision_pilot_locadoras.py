#!/usr/bin/env python3
"""Provision controlled pilot locadoras with real inventory files.

The script creates three pilot locadoras in the SQLite registry and writes one
inventory JSON per pilot unit. It intentionally requires explicit source
inventory files so the controlled pilot is backed by partner data, not by a
hardcoded mock.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.auth.branches import hash_password
from src.auth.registry import create_locadora_with_owner, registry_payload
from src.engine.inventory import parse_inventory_csv, parse_inventory_xlsx, save_inventory

SECTIONS = ("telescopic_shores", "tower_modules", "distribution_beams", "accessories")

PILOTS = {
    "complete": {
        "locadora": "Piloto Estoque Completo",
        "branch": "Matriz",
        "inventory": "pilot-complete",
        "description": "estoque completo",
    },
    "partial": {
        "locadora": "Piloto Estoque Parcial",
        "branch": "Matriz",
        "inventory": "pilot-partial",
        "description": "estoque parcial",
    },
    "custom": {
        "locadora": "Piloto Equipamentos Proprios",
        "branch": "Matriz",
        "inventory": "pilot-custom",
        "description": "escoras/torres proprias",
    },
}


def _read_inventory_source(path: Path, *, tenant_id: str, locadora: str) -> Dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif suffix == ".csv":
        payload = parse_inventory_csv(
            path.read_text(encoding="utf-8-sig"),
            tenant_id=tenant_id,
            locadora=locadora,
        )
    elif suffix == ".xlsx":
        payload = parse_inventory_xlsx(
            path.read_bytes(),
            tenant_id=tenant_id,
            locadora=locadora,
        )
    else:
        raise ValueError(f"Formato nao suportado para {path}: use .json, .csv ou .xlsx")

    payload = dict(payload or {})
    payload["tenant_id"] = tenant_id
    payload["locadora"] = locadora
    for section in SECTIONS:
        value = payload.get(section)
        payload[section] = value if isinstance(value, dict) else {}
    return payload


def _qty(item: Any) -> int:
    if isinstance(item, int):
        return item
    if isinstance(item, dict):
        return int(item.get("qty", 0))
    return 0


def _metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    section_models = {section: len(payload.get(section, {}) or {}) for section in SECTIONS}
    section_nonzero = {
        section: sum(1 for item in (payload.get(section, {}) or {}).values() if _qty(item) > 0)
        for section in SECTIONS
    }
    specs = 0
    for section in ("telescopic_shores", "tower_modules"):
        for item in (payload.get(section, {}) or {}).values():
            if isinstance(item, dict) and any(
                item.get(field) not in (None, "", [])
                for field in ("capacity_kn", "height_min_m", "height_max_m", "capacity_curve")
            ):
                specs += 1
    return {
        "models_by_section": section_models,
        "nonzero_by_section": section_nonzero,
        "total_models": sum(section_models.values()),
        "total_nonzero": sum(section_nonzero.values()),
        "models_with_custom_specs": specs,
    }


def _validate_profiles(payloads: Dict[str, Dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    complete = _metrics(payloads["complete"])
    partial = _metrics(payloads["partial"])
    custom = _metrics(payloads["custom"])

    for section in ("telescopic_shores", "tower_modules", "distribution_beams"):
        if complete["nonzero_by_section"][section] <= 0:
            errors.append(f"complete precisa ter estoque em {section}")

    if partial["total_nonzero"] <= 0:
        errors.append("partial precisa ter pelo menos um item com quantidade")
    if partial["total_models"] >= complete["total_models"]:
        errors.append("partial deveria ter menos modelos que complete")

    if custom["models_with_custom_specs"] <= 0:
        errors.append("custom precisa ter escora/torre com capacidade, altura ou curva propria")
    return errors


def _find_existing_user(username: str) -> Dict[str, str] | None:
    for loc in registry_payload().get("locadoras", []):
        for user in loc.get("users", []):
            if user.get("username") != username:
                continue
            branch = (loc.get("branches") or [{}])[0]
            return {
                "locadora_id": loc["id"],
                "branch_id": branch.get("id", ""),
                "inventory_name": branch.get("inventory_name", ""),
                "username": username,
            }
    return None


def provision_pilots(args: argparse.Namespace) -> Dict[str, Any]:
    if args.data_dir:
        os.environ["ESCORA_DATA_DIR"] = str(Path(args.data_dir).resolve())

    sources = {
        "complete": Path(args.complete).resolve(),
        "partial": Path(args.partial).resolve(),
        "custom": Path(args.custom).resolve(),
    }
    for key, path in sources.items():
        if not path.exists():
            raise FileNotFoundError(f"Inventario {key} nao encontrado: {path}")

    payloads = {
        key: _read_inventory_source(
            path,
            tenant_id=PILOTS[key]["inventory"],
            locadora=PILOTS[key]["locadora"],
        )
        for key, path in sources.items()
    }
    errors = _validate_profiles(payloads)
    if errors:
        raise ValueError("; ".join(errors))

    summary = {"dry_run": args.dry_run, "pilots": []}
    for key, payload in payloads.items():
        pilot = PILOTS[key]
        username = f"{args.email_prefix}-{key}@{args.email_domain}".lower()
        created = None
        if not args.dry_run:
            existing = _find_existing_user(username)
            if existing:
                created = existing
            else:
                if not args.owner_password:
                    raise ValueError("--owner-password e obrigatorio fora de --dry-run")
                created = create_locadora_with_owner(
                    name=pilot["locadora"],
                    owner_name=f"Owner {pilot['locadora']}",
                    owner_email=username,
                    owner_phone="",
                    password_hash=hash_password(args.owner_password),
                    branch_name=pilot["branch"],
                    inventory_name=pilot["inventory"],
                )
                if created is None:
                    raise ValueError(f"Nao foi possivel criar piloto {key}")
            save_inventory(created["inventory_name"], payload)
        summary["pilots"].append(
            {
                "key": key,
                "description": pilot["description"],
                "username": username,
                "branch_id": (created or {}).get("branch_id", ""),
                "inventory_name": (created or {}).get("inventory_name", pilot["inventory"]),
                "source": str(sources[key]),
                "metrics": _metrics(payload),
            }
        )
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provisiona tres locadoras piloto controladas a partir de inventarios reais.",
    )
    parser.add_argument("--complete", required=True, help="Inventario real de estoque completo (.json/.csv/.xlsx)")
    parser.add_argument("--partial", required=True, help="Inventario real de estoque parcial (.json/.csv/.xlsx)")
    parser.add_argument("--custom", required=True, help="Inventario real com escoras/torres proprias (.json/.csv/.xlsx)")
    parser.add_argument("--owner-password", default="", help="Senha inicial dos owners criados")
    parser.add_argument("--email-prefix", default="piloto", help="Prefixo dos emails de owner")
    parser.add_argument("--email-domain", default="estrutura.app", help="Dominio dos emails de owner")
    parser.add_argument("--data-dir", default="", help="ESCORA_DATA_DIR destino; opcional")
    parser.add_argument("--dry-run", action="store_true", help="Valida fontes e imprime resumo sem gravar")
    return parser


def main() -> int:
    try:
        summary = provision_pilots(_parser().parse_args())
    except Exception as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
