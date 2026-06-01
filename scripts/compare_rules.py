"""Compare Orguel decision rules against current Escora.AI engine logic.

Reads decision_rules from orguel_rules_extracted.json and evaluates
whether our engine's decision logic matches what Orguel engineers do.

This is NOT a constant-comparison — it checks CRITERIA alignment:
- Does our tower decision fire under the same conditions?
- Does our spacing adapt to the same structural signals?
- Are we missing rules that Orguel applies implicitly?

Usage:
    python3 scripts/compare_rules.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.constants import (
    ESPACAMENTO_MAX_DEFAULT, ESPACAMENTO_MAX_VIGA,
    DISTANCIA_PILAR_MIN, DISTANCIA_BORDA_MIN,
)
from src.engine.tower_selector import (
    BEAM_TOWER_FRACTION, SLAB_TOWER_FRACTION_THICK,
    SLAB_TOWER_FRACTION_LARGE, MIXED_TOWER_GRID_SPACING,
    BEAM_INTERMEDIATE_SPAN_MIN_M, BEAM_INTERMEDIATE_SPAN_MAX_M,
    CIMBRAMENTO_SPAN_M,
)


def load_analysis(path="data/analysis/orguel_rules_extracted.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_report(data: dict) -> str:
    rules = data.get("decision_rules", {})
    lines = []

    lines.append("# Comparação: Critérios de Decisão Orguel vs Escora.AI")
    lines.append("")
    lines.append(f"Entidades analisadas: {data.get('entity_count', 0)}")
    lines.append(f"Arquivos: {len(data.get('per_file', []))}")
    lines.append("")

    # =====================================================================
    # BEAMS: Tower vs Shore
    # =====================================================================
    r = rules.get("beam_tower_vs_shore", {})
    if r:
        lines.append("## 1. Vigas: Quando Torre vs Escora?")
        lines.append("")
        lines.append(f"Orguel usa **{r.get('tower_fraction', 0):.0%}** torres em vigas "
                     f"({r.get('n_towers', 0)} torres, {r.get('n_shores', 0)} escoras)")
        lines.append("")

        # Pillar proximity
        if "tower_dist_to_pillar" in r:
            tp = r["tower_dist_to_pillar"]
            sp = r["shore_dist_to_pillar"]
            lines.append("### 1a. Proximidade ao pilar")
            lines.append(f"- Torres → pilar: median **{tp['median']:.2f}m** (p25={tp['p25']:.2f}, p75={tp['p75']:.2f})")
            lines.append(f"- Escoras → pilar: median **{sp['median']:.2f}m** (p25={sp['p25']:.2f}, p75={sp['p75']:.2f})")
            lines.append(f"- Insight: {r.get('insight_pillar', 'N/A')}")
            if tp["median"] < sp["median"]:
                lines.append(f"- **REGRA**: Torres tendem a ficar mais perto dos pilares → "
                            f"são colocadas nos pontos de maior reação (apoios)")
            lines.append("")

        # Beam intersections
        if "tower_at_intersection_pct" in r:
            lines.append("### 1b. Interseções de vigas")
            lines.append(f"- Torres em interseções: **{r['tower_at_intersection_pct']:.0%}**")
            lines.append(f"- Escoras em interseções: **{r['shore_at_intersection_pct']:.0%}**")
            if r["tower_at_intersection_pct"] > r["shore_at_intersection_pct"] * 1.3:
                lines.append("- **REGRA**: Torres preferencialmente em nós de vigas (cruzamentos)")
            lines.append("")

        # Position along beam
        if "tower_near_beam_ends_pct" in r:
            lines.append("### 1c. Posição na viga")
            lines.append(f"- Torres nos extremos da viga (t<0.15 ou t>0.85): "
                        f"**{r['tower_near_beam_ends_pct']:.0%}**")
            if r["tower_near_beam_ends_pct"] > 0.30:
                lines.append("- **REGRA**: Torres concentradas nos apoios/extremidades da viga")
            elif r["tower_near_beam_ends_pct"] < 0.15:
                lines.append("- **REGRA**: Torres distribuídas ao longo da viga (não concentradas nos extremos)")
            lines.append("")

        # Beam length correlation
        if "tower_beam_length" in r and "shore_beam_length" in r:
            tl = r["tower_beam_length"]
            sl = r["shore_beam_length"]
            lines.append("### 1d. Comprimento da viga")
            lines.append(f"- Vigas com torres: median **{tl['median']:.2f}m** (p25={tl['p25']:.2f}, p75={tl['p75']:.2f})")
            lines.append(f"- Vigas com escoras: median **{sl['median']:.2f}m** (p25={sl['p25']:.2f}, p75={sl['p75']:.2f})")
            lines.append("")

        # Compare with our engine
        lines.append("### Escora.AI atual")
        lines.append(f"- `BEAM_TOWER_FRACTION = {BEAM_TOWER_FRACTION}` (fração fixa)")
        lines.append(f"- `CIMBRAMENTO_SPAN_M = {CIMBRAMENTO_SPAN_M}m` (acima → 100% torre)")
        lines.append(f"- `BEAM_INTERMEDIATE_SPAN = {BEAM_INTERMEDIATE_SPAN_MIN_M}-{BEAM_INTERMEDIATE_SPAN_MAX_M}m` (misto)")
        lines.append(f"- **Problema**: fração fixa não reflete critério estrutural — "
                    f"Orguel coloca torres ONDE a carga exige, não em X% das posições")
        lines.append("")

    # =====================================================================
    # SLABS: Tower vs Shore
    # =====================================================================
    r = rules.get("slab_tower_vs_shore", {})
    if r:
        lines.append("## 2. Lajes: Quando Torre vs Escora?")
        lines.append("")
        lines.append(f"Orguel usa **{r.get('tower_fraction', 0):.0%}** torres em lajes "
                     f"({r.get('n_towers', 0)} torres, {r.get('n_shores', 0)} escoras)")
        lines.append("")

        if "insight_beam_proximity" in r:
            lines.append("### 2a. Proximidade à viga")
            lines.append(f"- {r['insight_beam_proximity']}")
            if "tower_dist_to_beam" in r:
                tb = r["tower_dist_to_beam"]
                sb = r["shore_dist_to_beam"]
                lines.append(f"- Torre→viga: median **{tb['median']:.2f}m**")
                lines.append(f"- Escora→viga: median **{sb['median']:.2f}m**")
            lines.append("")

        lines.append("### Escora.AI atual")
        lines.append(f"- `SLAB_TOWER_FRACTION_THICK = {SLAB_TOWER_FRACTION_THICK}` (laje ≥20cm)")
        lines.append(f"- `SLAB_TOWER_FRACTION_LARGE = {SLAB_TOWER_FRACTION_LARGE}` (laje ≥40m²)")
        lines.append(f"- **Problema**: mesma fração fixa — não diferencia zona de carga alta vs baixa")
        lines.append("")

    # =====================================================================
    # SPACING PATTERNS
    # =====================================================================
    sp = rules.get("spacing_patterns", {})
    if sp:
        lines.append("## 3. Padrões de Espaçamento")
        lines.append("")

        for key, data in sp.items():
            lines.append(f"### {key}")
            if "near_pillar_spacing" in data:
                ns = data["near_pillar_spacing"]
                fs = data["far_pillar_spacing"]
                densify = data.get("densifies_near_pillar", False)
                ratio = data.get("ratio", 1.0)
                lines.append(f"- Perto do pilar (<2m): median **{ns['median']:.2f}m**")
                lines.append(f"- Longe do pilar (>3m): median **{fs['median']:.2f}m**")
                if densify:
                    lines.append(f"- **REGRA DETECTADA**: Densifica {1/ratio:.0%}× mais perto do pilar")
                else:
                    lines.append(f"- Sem densificação significativa (ratio {ratio:.2f})")
            if "near_beam_end_spacing" in data:
                es = data["near_beam_end_spacing"]
                ms = data["mid_beam_spacing"]
                densify = data.get("densifies_near_ends", False)
                lines.append(f"- Extremos da viga: median **{es['median']:.2f}m**")
                lines.append(f"- Meio da viga: median **{ms['median']:.2f}m**")
                if densify:
                    lines.append(f"- **REGRA DETECTADA**: Espaçamento mais apertado nos extremos")
            lines.append("")

        lines.append("### Escora.AI atual")
        lines.append(f"- `ESPACAMENTO_MAX_DEFAULT = {ESPACAMENTO_MAX_DEFAULT}m` (laje — fixo)")
        lines.append(f"- `ESPACAMENTO_MAX_VIGA = {ESPACAMENTO_MAX_VIGA}m` (viga — fixo)")
        lines.append(f"- `DISTANCIA_PILAR_MIN = {DISTANCIA_PILAR_MIN}m` (exclusão)")
        lines.append(f"- **Problema**: espaçamento uniforme — não densifica perto de pilares/apoios")
        lines.append("")

    # =====================================================================
    # VM PATTERNS
    # =====================================================================
    vm = rules.get("vm_patterns", {})
    if vm:
        lines.append("## 4. Padrões de VMs")
        lines.append(f"- Total: {vm.get('total_vms', 0)}")
        lines.append(f"- Perto de vigas (<2m): {vm.get('pct_near_beam', 0):.0%}")
        for key in ("spacing_viga", "spacing_laje"):
            if key in vm:
                s = vm[key]
                lines.append(f"- {key}: median **{s['median']:.2f}m** "
                            f"(p25={s['p25']:.2f}, p75={s['p75']:.2f})")
        lines.append("")

    # =====================================================================
    # RECOMMENDATIONS
    # =====================================================================
    lines.append("## 5. Recomendações para o Motor")
    lines.append("")
    lines.append("### 5a. Tower placement: de fração fixa para posição estrutural")
    lines.append("Em vez de `BEAM_TOWER_FRACTION = 0.35` (troca X% das posições),")
    lines.append("o motor deve colocar torres onde a carga é máxima:")
    lines.append("- Nos apoios (nós viga-pilar)")
    lines.append("- Nas interseções de vigas sem pilar")
    lines.append("- No meio de vãos grandes (reação máxima)")
    lines.append("E escoras onde a carga é menor (entre apoios, vãos curtos).")
    lines.append("")
    lines.append("### 5b. Espaçamento: de constante fixa para função da carga")
    lines.append("Em vez de `ESPACAMENTO_MAX = 1.10m` (igual em toda a laje),")
    lines.append("o motor deve calcular espaçamento a partir de:")
    lines.append("- Carga por m² na zona (peso concreto × espessura + sobrecarga)")
    lines.append("- Capacidade da escora na altura do projeto")
    lines.append("- Resultado: `spacing = sqrt(capacidade_escora / carga_m2)`")
    lines.append("Isso gera automaticamente espaçamento menor em lajes grossas")
    lines.append("e maior em lajes finas — como Orguel faz.")
    lines.append("")
    lines.append("### 5c. Densificação próxima a pilares")
    if sp and any(data.get("densifies_near_pillar") for data in sp.values()):
        lines.append("DETECTADO: Orguel densifica o espaçamento perto dos pilares.")
        lines.append("Implementar: reduzir espaçamento em 20-30% dentro de 2m do pilar")
        lines.append("(zona de punção — maior concentração de esforços).")
    else:
        lines.append("Não detectado com clareza nos dados atuais.")
    lines.append("")

    # Per-file table
    lines.append("## 6. Resumo por Arquivo")
    lines.append("")
    lines.append("| Arquivo | Torres V | ESC V | Torres L | ESC L | Fração T(V) | Fração T(L) |")
    lines.append("|---------|----------|-------|----------|-------|-------------|-------------|")
    for pf in data.get("per_file", []):
        lines.append(
            f"| {pf['filename'][:50]} | {pf['torre_viga']} | {pf['esc_viga']} | "
            f"{pf['torre_laje']} | {pf['esc_laje']} | "
            f"{pf['tower_fraction_viga']:.0%} | {pf['tower_fraction_laje']:.0%} |"
        )
    lines.append("")

    return "\n".join(lines)


def main():
    project_root = Path(__file__).parent.parent
    import os
    os.chdir(project_root)

    path = "data/analysis/orguel_rules_extracted.json"
    if not Path(path).exists():
        print(f"ERROR: {path} not found. Run analyze_orguel_rules.py first.")
        sys.exit(1)

    data = load_analysis(path)
    report = generate_report(data)

    output = Path("data/analysis/rule_comparison.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\nSaved to {output}")


if __name__ == "__main__":
    main()
