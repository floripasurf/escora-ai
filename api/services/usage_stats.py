"""Telemetria de piloto — agrega a tabela `jobs` existente (sem tabela nova).

Para acompanhar parceiros no teste sem depender de conversa manual: volume,
taxa de erro, tempo médio e quantos resultados exigiram revisão de engenharia.
"""

from typing import Any, Dict, List


def summarize_jobs(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Resumo agregado de uma lista de jobs (dicts do job_service).

    Campos usados: status, created_at/updated_at (datetime), results_data
    (dict com requires_review). Robusto a campos ausentes/None.
    """
    total = len(jobs)
    by_status: Dict[str, int] = {}
    for j in jobs:
        st = j.get("status") or "unknown"
        by_status[st] = by_status.get(st, 0) + 1

    errors = by_status.get("error", 0)
    error_rate = round(errors / total, 3) if total else 0.0

    requires_review = sum(
        1 for j in jobs if (j.get("results_data") or {}).get("requires_review")
    )

    elapsed: List[float] = []
    for j in jobs:
        if j.get("status") != "done":
            continue
        created, updated = j.get("created_at"), j.get("updated_at")
        if created is None or updated is None:
            continue
        try:
            dt = (updated - created).total_seconds()
        except TypeError:
            continue
        if dt >= 0:
            elapsed.append(dt)
    avg_elapsed = round(sum(elapsed) / len(elapsed), 1) if elapsed else None

    return {
        "total": total,
        "by_status": by_status,
        "error_rate": error_rate,
        "requires_review": requires_review,
        "avg_elapsed_seconds": avg_elapsed,
    }
