"""Perfil de metodologia por locadora/branch (manual §28.9).

A metodologia de escoramento e um ATRIBUTO DA LOCADORA (mesma logica da
hierarquia de fontes: "o catalogo da locadora dita"). O perfil define os
DEFAULTS do pipeline; flags explicitas do chamador sempre vencem
(§28.9 regra 1/2).

Persistencia: campo opcional ``metodologia`` em ``data/locadoras.json``
(ou no arquivo apontado por ``ESCORA_LOCADORAS_FILE``), tanto no nivel da
locadora quanto no nivel do branch (branch sobrescreve locadora). O JSON
NUNCA e escrito por este modulo — leitura opcional apenas; na ausencia do
campo valem os DEFAULTS em codigo abaixo.

Exemplo de JSON:
    {"locadoras": [{
        "id": "orguel",
        "metodologia": {"laje_layout": "line_first"},
        "branches": [{
            "id": "orguel-sjc",
            "metodologia": {"passo_sob_viga_m": 0.55}
        }]
    }]}
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Valores validos por campo categorico (§28.9; doka_124 pendente)
LAJE_LAYOUTS = ("grid_vm_duplo", "line_first")
EIXO_GUIAS_VALUES = ("unico_pavimento", "por_painel")
COBERTURA_VALUES = ("padrao", "torre_first")
BARROTES_ESCOPO_VALUES = ("locadora", "cliente")

# Rotulos pt-BR para rastreabilidade em relatorios (camada de modelo; os
# rotulos pt/en estruturados para a UI ficam em api/services/methodology_view).
_LAJE_LAYOUT_PT = {
    "grid_vm_duplo": "Grid VM duplo",
    "line_first": "Line-first Orguel",
}


def describe_methodology(methodology: Optional[Dict[str, Any]]) -> str:
    """Frase pt-BR de rastreabilidade para PDF/CSV (§28.9).

    Recebe o dict efetivo anexado ao PipelineResult (perfil cru + chave
    ``efetivo`` + ``origem``). Responde "qual metodologia gerou este desenho".
    """
    if not methodology:
        return "Metodologia: padrão (grid VM duplo)"
    layout = methodology.get("laje_layout", "grid_vm_duplo")
    parts = [_LAJE_LAYOUT_PT.get(layout, layout)]
    # Barrote: campo explicito (Fase 5); fallback p/ inferencia em dados antigos.
    escopo = methodology.get("barrotes_escopo")
    if escopo is None:
        escopo = "cliente" if layout == "line_first" else "locadora"
    # "por conta de" = RESPONSABILIDADE pela camada de barrotes (madeira); nao
    # implica inclusao no romaneio (barrotes de madeira nao sao quantificados).
    if escopo == "cliente":
        parts.append("barrotes por conta do cliente")
    else:
        parts.append("barrotes por conta da locadora")
    efetivo = methodology.get("efetivo") or {}
    passo = efetivo.get("passo_sob_viga_m")
    if passo:
        parts.append(f"passo sob viga {float(passo):.2f} m")
    if efetivo.get("cobertura_torre_first"):
        parts.append("cobertura torre-first")
    if methodology.get("origem") == "override":
        parts.append("(override do projeto)")
    return "Metodologia: " + " · ".join(parts)


@dataclass(frozen=True)
class MethodologyProfile:
    """Perfil de metodologia (§28.9) — defaults do perfil grid legado.

    Campos:
        laje_layout: "grid_vm_duplo" (malha VM130+VM80, legado) ou
            "line_first" (gold standard Orguel, §28.8).
        eixo_guias: "unico_pavimento" (malha de pavimento — decisao do
            revisor v8) ou "por_painel" (pratica Orguel literal).
        escoras_equidistantes: L/n constante por guia continua (v7).
        passo_sob_viga_m: passo do conjunto escora+cruzeta sob viga.
            0.80 (DOCX §10.3, legado) ou 0.50-0.65 (gold standard §28.8
            item 7; conflito registrado em §23.9).
        tripes_fracao: fracao de tripes sobre o total de escoras
            (nota 17 Orguel: 0.30; negociavel por obra).
        cobertura: "padrao" ou "torre_first" (gold standard item 10:
            vigas de cobertura apoiadas em torres a 1.25-1.65 m c-a-c).
        min_dist_escoras_m: distancia minima global entre escoras
            (audit OP-102 / v10).

    Barrotes (Fase 5 — atributo EXPLICITO da locadora, antes inferido de
    laje_layout):
        barrotes_escopo: quem fornece a camada de BARROTES (madeira) sobre as
            guias — "locadora" (faz parte do servico) ou "cliente" (por conta
            da obra; caso Orguel, nota 15 gold standard §28.8).

    IMPORTANTE: este campo descreve APENAS a camada de barrotes de madeira do
    cliente. Ele NAO controla as secundarias VM metalicas geradas pelo engine
    (VM80 do grid e do sistema nervurado ALU14+VM80): estas sao GUIAS
    ESTRUTURAIS, dirigidas por laje_layout/nervura, sempre desenhadas e
    quantificadas quando estruturalmente necessarias (decisao de produto
    2026-06). Por isso nao ha flags de desenhar/quantificar/modelo/passo aqui.
    """

    laje_layout: str = "grid_vm_duplo"
    eixo_guias: str = "unico_pavimento"
    escoras_equidistantes: bool = True
    passo_sob_viga_m: float = 0.80
    tripes_fracao: float = 0.30
    cobertura: str = "padrao"
    min_dist_escoras_m: float = 0.30
    barrotes_escopo: str = "locadora"

    @property
    def slab_layout_mode(self) -> str:
        """Mapeia laje_layout para a flag slab_layout_mode do pipeline."""
        return "line_first" if self.laje_layout == "line_first" else "grid"

    def to_dict(self) -> Dict[str, Any]:
        """Serializa os campos do perfil (rastreabilidade, §28.9).

        Camada de modelo: apenas os campos crus do perfil, sem rotulos de UI
        (estes ficam em api/services/methodology_view). Usado pelo pipeline e
        pelos relatorios para registrar "qual metodologia gerou este desenho".
        """
        return {f.name: getattr(self, f.name) for f in fields(self)}


# Perfil grid legado (defaults da tabela §28.9): comportamento atual.
PROFILE_GRID_LEGACY = MethodologyProfile()

# Perfil Orguel/line-first (gold standard §28.8): passo sob viga 0.60
# (faixa 0.55-0.65 dos projetos reais) e cobertura torre-first (item 10).
PROFILE_ORGUEL_LINE_FIRST = MethodologyProfile(
    laje_layout="line_first",
    passo_sob_viga_m=0.60,
    cobertura="torre_first",
    barrotes_escopo="cliente",
)

# Base por laje_layout: um JSON que so diga {"laje_layout": "line_first"}
# herda os demais defaults do perfil line-first (passo 0.60 etc.).
_BASE_BY_LAYOUT: Dict[str, MethodologyProfile] = {
    "grid_vm_duplo": PROFILE_GRID_LEGACY,
    "line_first": PROFILE_ORGUEL_LINE_FIRST,
}

DEFAULT_LOCADORAS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "locadoras.json"
)


def _locadoras_path(path: Optional[str] = None) -> Path:
    if path:
        return Path(path)
    override = os.environ.get("ESCORA_LOCADORAS_FILE")
    return Path(override) if override else DEFAULT_LOCADORAS_PATH


def _coerce_field(name: str, value: Any) -> Optional[Any]:
    """Valida/coage um valor de campo do perfil; None = invalido (ignorar)."""
    if name == "laje_layout":
        return value if value in LAJE_LAYOUTS else None
    if name == "eixo_guias":
        return value if value in EIXO_GUIAS_VALUES else None
    if name == "cobertura":
        return value if value in COBERTURA_VALUES else None
    if name == "barrotes_escopo":
        return value if value in BARROTES_ESCOPO_VALUES else None
    if name == "escoras_equidistantes":
        return value if isinstance(value, bool) else None
    if name in ("passo_sob_viga_m", "tripes_fracao", "min_dist_escoras_m"):
        try:
            v = float(value)
        except (TypeError, ValueError):
            return None
        if name == "passo_sob_viga_m" and not (0.20 <= v <= 2.00):
            return None
        if name == "tripes_fracao" and not (0.0 <= v <= 1.0):
            return None
        if name == "min_dist_escoras_m" and not (0.05 <= v <= 1.00):
            return None
        return v
    return None


def profile_from_dict(data: Optional[Dict[str, Any]]) -> MethodologyProfile:
    """Constroi um perfil a partir de um dict (campo ``metodologia``).

    Campos ausentes herdam do perfil-base do ``laje_layout`` informado
    (grid legado quando omitido). Valores invalidos sao ignorados com
    warning — nunca quebram o pipeline.
    """
    data = data or {}
    layout = data.get("laje_layout")
    if layout is not None and layout not in LAJE_LAYOUTS:
        logger.warning(
            f"Perfil de metodologia: laje_layout invalido '{layout}' — "
            f"usando default grid_vm_duplo (§28.9)"
        )
        layout = None
    base = _BASE_BY_LAYOUT.get(layout or "grid_vm_duplo", PROFILE_GRID_LEGACY)

    overrides: Dict[str, Any] = {}
    known = {f.name for f in fields(MethodologyProfile)}
    for key, raw in data.items():
        if key == "laje_layout" or key not in known:
            continue
        coerced = _coerce_field(key, raw)
        if coerced is None:
            logger.warning(
                f"Perfil de metodologia: valor invalido para '{key}' "
                f"({raw!r}) — mantendo default {getattr(base, key)!r}"
            )
            continue
        overrides[key] = coerced
    return replace(base, **overrides) if overrides else base


def load_methodology(
    branch_id: Optional[str] = None,
    locadora_id: Optional[str] = None,
    path: Optional[str] = None,
) -> MethodologyProfile:
    """Carrega o perfil de metodologia da locadora/branch (§28.9).

    Procura o campo ``metodologia`` em ``data/locadoras.json`` (ou no
    arquivo de ``ESCORA_LOCADORAS_FILE``): primeiro no nivel da locadora,
    depois no branch (que sobrescreve campo a campo). Qualquer falha de
    leitura/parse retorna os DEFAULTS em codigo — leitura sempre opcional.
    """
    file_path = _locadoras_path(path)
    if not file_path.exists():
        return PROFILE_GRID_LEGACY
    try:
        registry = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Perfil de metodologia: falha lendo {file_path}: {exc}")
        return PROFILE_GRID_LEGACY

    loc_meta: Optional[Dict[str, Any]] = None
    branch_meta: Optional[Dict[str, Any]] = None
    for loc in registry.get("locadoras", []):
        branches = loc.get("branches", []) or []
        branch_match = (
            next((b for b in branches if b.get("id") == branch_id), None)
            if branch_id
            else None
        )
        loc_match = locadora_id is not None and loc.get("id") == locadora_id
        if branch_match is None and not loc_match:
            continue
        meta = loc.get("metodologia")
        if isinstance(meta, dict):
            loc_meta = meta
        if branch_match is not None:
            b_meta = branch_match.get("metodologia")
            if isinstance(b_meta, dict):
                branch_meta = b_meta
        break

    if loc_meta is None and branch_meta is None:
        return PROFILE_GRID_LEGACY
    merged: Dict[str, Any] = dict(loc_meta or {})
    merged.update(branch_meta or {})
    return profile_from_dict(merged)
