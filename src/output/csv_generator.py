"""CSVs auxiliares de saída — consumo por pé-direito.

Centraliza CSVs gerados a partir de `ReportData`. Por enquanto apenas o
resumo de consumo por pé-direito (`*_consumo.csv`).
"""

import csv
from typing import List

from src.output.report_data import ReportData


CONSUMPTION_FIELDNAMES = [
    "pe_direito_m",
    "area_m2",
    "volume_bruto_m3",
    "volume_liquido_m3",
    "escoras_kg",
    "acessorios_kg",
    "total_kg",
    "taxa_kg_m3_bruto",
    "taxa_kg_m3_liquido",
    "taxa_kg_m2",
    "categoria",
]


def write_consumption_csv(report: ReportData, output_path: str) -> str:
    """Escreve CSV de consumo por (pé-direito, categoria) + linha TOTAL.

    Layout:
        pe_direito_m;area_m2;volume_bruto_m3;volume_liquido_m3;
        escoras_kg;acessorios_kg;total_kg;
        taxa_kg_m3_bruto;taxa_kg_m3_liquido;taxa_kg_m2;categoria

    Args:
        report: Dados normalizados do projeto.
        output_path: Caminho do arquivo a ser escrito.

    Returns:
        O `output_path` recebido.
    """
    rows: List[dict] = []
    for r in report.consumption_rows:
        rows.append({
            "pe_direito_m": _fmt(r.pe_direito_m),
            "area_m2": _fmt(r.area_m2),
            "volume_bruto_m3": _fmt(r.volume_bruto_m3),
            "volume_liquido_m3": _fmt(r.volume_liquido_m3),
            "escoras_kg": _fmt(r.shores_weight_kg),
            "acessorios_kg": _fmt(r.accessories_weight_kg),
            "total_kg": _fmt(r.total_weight_kg),
            "taxa_kg_m3_bruto": _fmt(r.rate_kg_m3_bruto),
            "taxa_kg_m3_liquido": _fmt(r.rate_kg_m3_liquido),
            "taxa_kg_m2": _fmt(r.rate_kg_m2),
            "categoria": r.category_label,
        })

    totals = report.consumption_totals or {}
    if totals:
        rows.append({
            "pe_direito_m": "TOTAL",
            "area_m2": _fmt(totals.get("area_m2", 0.0)),
            "volume_bruto_m3": _fmt(totals.get("volume_bruto_m3", 0.0)),
            "volume_liquido_m3": _fmt(totals.get("volume_liquido_m3", 0.0)),
            "escoras_kg": _fmt(totals.get("shores_kg", 0.0)),
            "acessorios_kg": _fmt(totals.get("accessories_kg", 0.0)),
            "total_kg": _fmt(totals.get("total_kg", 0.0)),
            "taxa_kg_m3_bruto": _fmt(totals.get("rate_kg_m3_bruto", 0.0)),
            "taxa_kg_m3_liquido": _fmt(totals.get("rate_kg_m3_liquido", 0.0)),
            "taxa_kg_m2": _fmt(totals.get("rate_kg_m2", 0.0)),
            "categoria": "",
        })

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CONSUMPTION_FIELDNAMES, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def _fmt(value) -> str:
    """Formata número com vírgula decimal (padrão BR) ou retorna string."""
    if isinstance(value, str):
        return value
    try:
        f = float(value)
    except (TypeError, ValueError):
        return ""
    if f == int(f):
        return str(int(f))
    return f"{f:.2f}".replace(".", ",")
