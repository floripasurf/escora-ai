"""Geração de lista de materiais (Bill of Materials)."""

import csv
from typing import List, Dict
from src.models.project import ShoringResult


def generate_bom(results: List[ShoringResult]) -> List[Dict[str, any]]:
    """
    Gera lista de materiais consolidada.
    Agrupa por modelo de escora.
    """
    bom: Dict[str, Dict] = {}

    for result in results:
        for shore in result.shores:
            model_id = shore.shore.id
            if model_id not in bom:
                bom[model_id] = {
                    "modelo": shore.shore.model,
                    "fabricante": shore.shore.manufacturer,
                    "id": model_id,
                    "quantidade": 0,
                    "capacidade_kn": shore.shore.load_capacity_kn,
                    "altura_min_m": shore.shore.height_min_m,
                    "altura_max_m": shore.shore.height_max_m,
                    "peso_unitario_kg": shore.shore.weight_kg,
                    "preco_unitario_brl": shore.shore.price_reference_brl,
                }
            bom[model_id]["quantidade"] += 1

    # Calcular totais
    rows = []
    for entry in bom.values():
        entry["peso_total_kg"] = entry["quantidade"] * entry["peso_unitario_kg"]
        entry["preco_total_brl"] = entry["quantidade"] * entry["preco_unitario_brl"]
        rows.append(entry)

    return rows


def write_bom_csv(results: List[ShoringResult], output_path: str) -> str:
    """Escreve a lista de materiais em CSV."""
    rows = generate_bom(results)

    fieldnames = [
        "id",
        "modelo",
        "fabricante",
        "quantidade",
        "capacidade_kn",
        "altura_min_m",
        "altura_max_m",
        "peso_unitario_kg",
        "peso_total_kg",
        "preco_unitario_brl",
        "preco_total_brl",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path
