"""Gerador de diagramas Mermaid.js a partir do CalculationResult.

Produz dois tipos de diagrama:
1. Fluxo de decisão — mostra qual regra disparou para cada viga/laje
2. Resumo do projeto — visão geral do escoramento com quantidades

Os diagramas são strings Mermaid puras, prontas para renderização via
mermaid.js no frontend ou inclusão em relatórios markdown/HTML.
"""

from typing import Dict
from src.models.calculation_models import CalculationResult


# Mapeamento de decision_rule → descrição curta em PT
RULE_LABELS = {
    "rule-1-altura": "Altura > 4.5m",
    "rule-1b-carga": "Carga > capacidade escora",
    "rule-sem-estoque-torre": "Sem torres em estoque",
    "rule-16-externa": "Viga externa pequena",
    "rule-16c-viga-grande": "Vão > 10m (cimbramento)",
    "rule-16b-viga-media": "Vão 6-10m (1 torre central)",
    "rule-5-viga-mista": "Viga mista (torres estruturais)",
    "rule-4-laje-espessa": "Laje espessa ≥ 20cm",
    "rule-5-laje-grande": "Laje grande ≥ 40m²",
    "rule-6-nervurada": "Laje nervurada",
    "rule-default-telescopic": "Escora telescópica (padrão)",
}

# Cores para os nós Mermaid por tipo de suporte
STYLE_TOWER = "fill:#e74c3c,color:#fff"
STYLE_MIXED = "fill:#f39c12,color:#fff"
STYLE_TELESCOPIC = "fill:#27ae60,color:#fff"
STYLE_HEADER = "fill:#2c3e50,color:#fff"


def generate_decision_diagram(calc: CalculationResult) -> str:
    """Gera diagrama de fluxo de decisão para cada elemento do projeto.

    Mostra a árvore de decisão do motor com destaque na regra que disparou
    para cada viga e laje processada.
    """
    lines = ["flowchart TD"]

    # Nó raiz
    lines.append(f'    START["🏗️ Projeto: {len(calc.beam_results)} vigas, '
                 f'{len(calc.slab_results)} lajes"]')
    lines.append(f"    style START {STYLE_HEADER}")

    # Árvore de decisão genérica
    lines.append('    START --> H{{"Altura > 4.5m?"}}')
    lines.append('    H -->|Sim| T1["100% Torre"]')
    lines.append(f"    style T1 {STYLE_TOWER}")
    lines.append('    H -->|Não| C{{"Carga > capacidade?"}}')
    lines.append('    C -->|Sim| T2["100% Torre"]')
    lines.append(f"    style T2 {STYLE_TOWER}")
    lines.append('    C -->|Não| V{{"É viga?"}}')

    # Branch: vigas
    lines.append('    V -->|Sim| VS{{"Vão da viga?"}}')
    lines.append('    VS -->|"> 10m"| VT["100% Torre<br/>cimbramento"]')
    lines.append(f"    style VT {STYLE_TOWER}")
    lines.append('    VS -->|"6-10m"| VM1["MISTO<br/>1 torre central"]')
    lines.append(f"    style VM1 {STYLE_MIXED}")
    lines.append('    VS -->|"< 6m"| VL{{"Laje ≥ 15cm?"}}')
    lines.append('    VL -->|Sim| VM2["MISTO<br/>torres estruturais"]')
    lines.append(f"    style VM2 {STYLE_MIXED}")
    lines.append('    VL -->|Não| VE["100% Escora"]')
    lines.append(f"    style VE {STYLE_TELESCOPIC}")

    # Branch: lajes
    lines.append('    V -->|Não| LS{{"Espessura / Área?"}}')
    lines.append('    LS -->|"≥ 20cm"| LM1["MISTO 18%<br/>torres em grid"]')
    lines.append(f"    style LM1 {STYLE_MIXED}")
    lines.append('    LS -->|"≥ 40m²"| LM2["MISTO 15%<br/>torres em grid"]')
    lines.append(f"    style LM2 {STYLE_MIXED}")
    lines.append('    LS -->|Padrão| LE["100% Escora"]')
    lines.append(f"    style LE {STYLE_TELESCOPIC}")

    return "\n".join(lines)


def generate_project_summary_diagram(calc: CalculationResult) -> str:
    """Gera diagrama de resumo do projeto com regras disparadas por elemento.

    Cada viga/laje aparece com a regra que o motor usou, conectada ao
    resultado (tipo de suporte + quantidade de escoras/torres).
    """
    lines = ["flowchart LR"]

    # Contadores globais
    total_beam_shores = sum(br.shore_count for br in calc.beam_results)
    total_slab_shores = sum(len(sr.shores) for sr in calc.slab_results)
    total = total_beam_shores + total_slab_shores

    lines.append(f'    P["🏗️ Projeto<br/>{total} escoras/torres"]')
    lines.append(f"    style P {STYLE_HEADER}")

    # Vigas
    if calc.beam_results:
        lines.append(f'    P --> BG["📐 Vigas<br/>{len(calc.beam_results)} vigas<br/>'
                     f'{total_beam_shores} suportes"]')
        lines.append(f"    style BG {STYLE_HEADER}")

        for i, br in enumerate(calc.beam_results):
            bid = f"B{i}"
            name = br.beam.name or f"Viga {i+1}"
            rule = br.decision_rule or "rule-default-telescopic"
            rule_label = RULE_LABELS.get(rule, rule)
            length = br.beam.length_m or 0

            # Contar torres vs escoras
            n_tower = sum(1 for s in br.shores
                          if getattr(s, "support_type", None)
                          and s.support_type.value == "tower")
            n_tele = br.shore_count - n_tower

            detail = f"{name}<br/>L={length:.1f}m | {br.shore_count} sup."
            if n_tower > 0:
                detail += f"<br/>🔴 {n_tower} torres + 🟢 {n_tele} escoras"
                style = STYLE_MIXED
            else:
                detail += f"<br/>🟢 {n_tele} escoras"
                style = STYLE_TELESCOPIC

            lines.append(f'    BG --> {bid}["{detail}"]')

            # Nó da regra
            rid = f"R{bid}"
            lines.append(f'    {bid} --> {rid}(["{rule_label}"])')
            lines.append(f"    style {bid} {style}")

    # Lajes
    if calc.slab_results:
        lines.append(f'    P --> SG["📏 Lajes<br/>{len(calc.slab_results)} painéis<br/>'
                     f'{total_slab_shores} suportes"]')
        lines.append(f"    style SG {STYLE_HEADER}")

        for i, sr in enumerate(calc.slab_results):
            sid = f"S{i}"
            label = sr.label if hasattr(sr, "label") and sr.label else f"Laje {i+1}"
            rule = sr.decision_rule or "rule-default-telescopic"
            rule_label = RULE_LABELS.get(rule, rule)
            area = sr.area_m2
            thick_cm = round(sr.thickness_m * 100)

            n_tower = sum(1 for s in sr.shores
                          if getattr(s, "support_type", None)
                          and s.support_type.value == "tower")
            n_tele = len(sr.shores) - n_tower

            detail = f"{label}<br/>A={area:.1f}m² e={thick_cm}cm"
            if n_tower > 0:
                detail += f"<br/>🔴 {n_tower} torres + 🟢 {n_tele} escoras"
                style = STYLE_MIXED
            else:
                detail += f"<br/>🟢 {n_tele} escoras"
                style = STYLE_TELESCOPIC

            lines.append(f'    SG --> {sid}["{detail}"]')

            rid = f"R{sid}"
            lines.append(f'    {sid} --> {rid}(["{rule_label}"])')
            lines.append(f"    style {sid} {style}")

    return "\n".join(lines)


def generate_spacing_diagram(calc: CalculationResult) -> str:
    """Gera diagrama mostrando o espaçamento adaptativo por laje.

    Compara o espaçamento usado vs o teto da tabela para cada laje,
    evidenciando onde o cálculo adaptativo reduziu o espaçamento.
    """
    lines = ["flowchart TD"]
    lines.append('    TITLE["📊 Espaçamento Adaptativo por Carga"]')
    lines.append(f"    style TITLE {STYLE_HEADER}")

    from src.engine.shore_capacity import get_max_spacing_by_thickness

    for i, sr in enumerate(calc.slab_results):
        sid = f"SL{i}"
        label = sr.label if hasattr(sr, "label") and sr.label else f"Laje {i+1}"
        thick_cm = round(sr.thickness_m * 100)
        teto = get_max_spacing_by_thickness(sr.thickness_m)

        # Espaçamento real usado
        sx = sr.spacing_x_m
        sy = sr.spacing_y_m
        avg_spacing = (sx + sy) / 2 if sx > 0 and sy > 0 else max(sx, sy)

        reduced = avg_spacing < teto - 0.05  # margem de 5cm

        detail = (f"{label} (e={thick_cm}cm)<br/>"
                  f"Teto: {teto:.2f}m")
        if reduced:
            detail += f"<br/>Usado: {avg_spacing:.2f}m ↓"
            style = "fill:#e67e22,color:#fff"
        else:
            detail += f"<br/>Usado: {avg_spacing:.2f}m ✓"
            style = STYLE_TELESCOPIC

        lines.append(f'    TITLE --> {sid}["{detail}"]')
        lines.append(f"    style {sid} {style}")

    return "\n".join(lines)


def generate_all_diagrams(calc: CalculationResult) -> Dict[str, str]:
    """Gera todos os diagramas disponíveis.

    Returns:
        Dict com chaves: 'decision_flow', 'project_summary', 'spacing'
    """
    return {
        "decision_flow": generate_decision_diagram(calc),
        "project_summary": generate_project_summary_diagram(calc),
        "spacing": generate_spacing_diagram(calc),
    }
