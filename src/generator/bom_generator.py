"""Geração de lista de materiais (Bill of Materials).

Manual §28 (2026-05-29): aggregate_vm_bom() consolida vigas metalicas do
grid gerado por src/engine/vm_grid_builder.py para o BOM final.
"""

import csv
from typing import Any, Dict, Iterable, List, Sequence
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

    # Volume escorado total do projeto (replicado em cada linha para
    # que ferramentas de orçamento possam consumir o CSV sem parser extra).
    volume_total_m3 = round(sum(r.volume_m3 for r in results), 2)

    # Calcular totais
    rows = []
    for entry in bom.values():
        entry["peso_total_kg"] = entry["quantidade"] * entry["peso_unitario_kg"]
        entry["preco_total_brl"] = entry["quantidade"] * entry["preco_unitario_brl"]
        entry["volume_m3_projeto"] = volume_total_m3
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
        "volume_m3_projeto",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


# ===========================================================================
# Manual §28: agregacao do BOM de VMs (vigas metalicas) do grid completo.
# Consome `vm_grid` de cada SlabShoringResult e produz linhas por modelo+
# comprimento. Indenpendente de ShoringResult (que e o modelo legado).
# ===========================================================================

def aggregate_vm_bom(slab_results: Iterable[Any]) -> List[Dict[str, Any]]:
    """Agrega o BOM de VMs a partir de uma colecao de SlabShoringResult.

    Cada slab_result pode ter um atributo ``vm_grid`` (VMGrid) com
    ``bom: dict[str, dict[int, int]]`` mapeando modelo -> comprimento_mm
    -> quantidade. Esta funcao soma quantidades cross-laje e calcula
    metragem total.

    Args:
        slab_results: iterable de SlabShoringResult (do pipeline).

    Returns:
        Lista de dicts {modelo, comprimento_mm, quantidade, metragem_total_m,
        role_principal} ordenados por modelo e comprimento.
    """
    aggregated: Dict[tuple, Dict[str, Any]] = {}
    for sr in slab_results:
        grid = getattr(sr, "vm_grid", None)
        if grid is None:
            continue
        bom = getattr(grid, "bom", None) or {}
        # Tambem precisamos do role principal de cada modelo (primaria vs
        # secundaria); inferir do segmento mais comum por modelo.
        role_by_model: Dict[str, str] = {}
        for seg in getattr(grid, "segments", []):
            role_by_model.setdefault(seg.model, seg.role)
        for model, lengths in bom.items():
            for length_mm, qty in lengths.items():
                key = (model, int(length_mm))
                if key not in aggregated:
                    aggregated[key] = {
                        "modelo": model,
                        "comprimento_mm": int(length_mm),
                        "quantidade": 0,
                        "metragem_total_m": 0.0,
                        "role_principal": role_by_model.get(model, ""),
                    }
                aggregated[key]["quantidade"] += int(qty)
                aggregated[key]["metragem_total_m"] = round(
                    aggregated[key]["quantidade"] * int(length_mm) / 1000.0,
                    2,
                )
    rows = sorted(
        aggregated.values(),
        key=lambda r: (r["modelo"], r["comprimento_mm"]),
    )
    return rows


def write_vm_bom_csv(
    slab_results: Iterable[Any],
    output_path: str,
) -> str:
    """Escreve BOM de VMs (vigas metalicas do grid) em CSV.

    Cabecalho:
        modelo, comprimento_mm, quantidade, metragem_total_m, role_principal
    """
    rows = aggregate_vm_bom(slab_results)
    fieldnames = [
        "modelo", "comprimento_mm", "quantidade",
        "metragem_total_m", "role_principal",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def aggregate_vm_summary(slab_results: Iterable[Any]) -> Dict[str, Dict[str, float]]:
    """Resumo simplificado por modelo (sem comprimento).

    Util para o relatorio Rich / dashboard:
        {model: {quantidade: int, metragem_total_m: float}}
    """
    rows = aggregate_vm_bom(slab_results)
    summary: Dict[str, Dict[str, float]] = {}
    for r in rows:
        m = r["modelo"]
        if m not in summary:
            summary[m] = {"quantidade": 0, "metragem_total_m": 0.0}
        summary[m]["quantidade"] += r["quantidade"]
        summary[m]["metragem_total_m"] = round(
            summary[m]["metragem_total_m"] + r["metragem_total_m"], 2,
        )
    return summary
