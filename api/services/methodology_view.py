"""Serializacao do perfil de metodologia para a API (Fase 2).

Converte um ``MethodologyProfile`` (``src/models/methodology.py``) num dict
JSON-friendly com rotulos legiveis pt/en, para consumo do frontend (badge,
/auth/me, /auth/login).

Fase 5: o resumo de barrote vem do campo EXPLICITO ``barrotes_escopo``
(locadora|cliente), nao mais inferido de ``laje_layout`` — ``inferido`` e
sempre ``False``. Refere-se a camada de barrotes de MADEIRA do cliente; nao
descreve as secundarias VM metalicas (guias estruturais do engine).
"""

from __future__ import annotations

from typing import Dict

from src.models.methodology import MethodologyProfile

_LAJE_LAYOUT_LABELS = {
    "grid_vm_duplo": {"pt": "Grid VM duplo", "en": "Double VM grid"},
    "line_first": {"pt": "Line-first Orguel", "en": "Line-first (Orguel)"},
}

_EIXO_GUIAS_LABELS = {
    "unico_pavimento": {"pt": "Único por pavimento", "en": "Single per floor"},
    "por_painel": {"pt": "Por painel", "en": "Per panel"},
}

_COBERTURA_LABELS = {
    "padrao": {"pt": "Padrão", "en": "Standard"},
    "torre_first": {"pt": "Torre-first", "en": "Tower-first"},
}

def _label(table: Dict, key: str) -> Dict[str, str]:
    return table.get(key, {"pt": key, "en": key})


def _barrote_resumo(profile: MethodologyProfile) -> Dict:
    """Resumo da camada de barrotes (madeira) a partir do escopo explicito."""
    # "por conta de" = responsabilidade pela camada de barrotes (madeira);
    # NAO implica que apareca no romaneio (barrotes de madeira nao sao
    # quantificados — so as guias VM estruturais entram no BOM).
    usa = profile.barrotes_escopo == "locadora"
    if usa:
        pt = "Barrotes por conta da locadora"
        en = "Joists are the rental company's responsibility"
    else:
        pt = "Barrotes por conta do cliente"
        en = "Joists are the client's responsibility"
    return {
        "usa_barrote": usa,
        "escopo": profile.barrotes_escopo,
        "inferido": False,
        "labels": {"pt": pt, "en": en},
    }


def serialize_profile(profile: MethodologyProfile) -> Dict:
    """Serializa o perfil de metodologia para JSON (campos + rotulos)."""
    layout = profile.laje_layout
    return {
        "laje_layout": layout,
        "eixo_guias": profile.eixo_guias,
        "escoras_equidistantes": profile.escoras_equidistantes,
        "passo_sob_viga_m": profile.passo_sob_viga_m,
        "tripes_fracao": profile.tripes_fracao,
        "cobertura": profile.cobertura,
        "min_dist_escoras_m": profile.min_dist_escoras_m,
        "barrotes_escopo": profile.barrotes_escopo,
        "labels": {
            "laje_layout": _label(_LAJE_LAYOUT_LABELS, layout),
            "eixo_guias": _label(_EIXO_GUIAS_LABELS, profile.eixo_guias),
            "cobertura": _label(_COBERTURA_LABELS, profile.cobertura),
        },
        "barrote_resumo": _barrote_resumo(profile),
    }
