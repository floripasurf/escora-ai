"""Identificacao do SISTEMA ESTRUTURAL — passo zero da cadeia (manual §5.1).

Pendencia 28 (manual §21): antes de classificar elementos, o Escora.AI deve
identificar QUAL sistema estrutural o projeto usa e rotear:

- CONCRETO_ARMADO       -> fluxo completo (foco do produto);
- PRE_MOLDADO           -> fluxo parcial da secao 7.1 (guias, contraflecha);
- ALVENARIA_ESTRUTURAL  -> fluxo parcial (laje sobre parede portante,
                           barrotes a <= 5 cm da alvenaria, secao 11.2);
- ESTRUTURA_METALICA    -> caso especial steel deck (revisao obrigatoria);
- WOOD_STEEL_FRAME      -> fora de escopo (sem concreto a escorar);
- PESADO_INFRA          -> bloqueio/revisao (OAE NBR 7187, protendido,
                           fundacoes profundas, valas NR-18).

Regra 3 da secao 5.1: sem identificacao confiante mas com pilares + vigas +
lajes -> assumir CONCRETO_ARMADO e registrar pendencia de confirmacao.

Complementa (nao substitui) o ``construction_classifier`` existente:
``ConstructionType`` responde "que obra e" (residencial/OAE/contencao);
``StructuralSystem`` responde "como a estrutura e suportada".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence

from src.parser.construction_classifier import ConstructionType


class StructuralSystem(str, Enum):
    """Sistema estrutural do projeto (manual §5.1)."""
    CONCRETO_ARMADO = "concreto_armado"
    PRE_MOLDADO = "pre_moldado"
    ALVENARIA_ESTRUTURAL = "alvenaria_estrutural"
    ESTRUTURA_METALICA = "estrutura_metalica"
    WOOD_STEEL_FRAME = "wood_steel_frame"
    PESADO_INFRA = "pesado_infra"
    UNKNOWN = "unknown"


class SystemRouting(str, Enum):
    """Roteamento do pipeline por sistema (manual §5.1)."""
    FULL = "full"                  # fluxo completo
    PARTIAL = "partial"            # fluxo parcial (7.1 / laje sobre parede)
    SPECIAL_REVIEW = "special"     # caso especial, revisao obrigatoria
    BLOCKED = "blocked"            # fora de escopo — bloquear saida


def routing_requires_review(routing: "SystemRouting") -> bool:
    """True quando o roteamento exige revisao de engenharia antes do uso.

    BLOCKED (fora de escopo) e SPECIAL_REVIEW (caso especial/UNKNOWN) nao
    devem ser entregues como projeto executivo automatico — o resultado e
    marcado como `requires_review` para a UI/API alertarem o parceiro.
    """
    return routing in (SystemRouting.BLOCKED, SystemRouting.SPECIAL_REVIEW)


ROUTING_BY_SYSTEM = {
    StructuralSystem.CONCRETO_ARMADO: SystemRouting.FULL,
    StructuralSystem.PRE_MOLDADO: SystemRouting.PARTIAL,
    StructuralSystem.ALVENARIA_ESTRUTURAL: SystemRouting.PARTIAL,
    StructuralSystem.ESTRUTURA_METALICA: SystemRouting.SPECIAL_REVIEW,
    StructuralSystem.WOOD_STEEL_FRAME: SystemRouting.BLOCKED,
    StructuralSystem.PESADO_INFRA: SystemRouting.BLOCKED,
    StructuralSystem.UNKNOWN: SystemRouting.SPECIAL_REVIEW,
}


@dataclass
class StructuralSystemResult:
    """Sistema detectado + roteamento + rastreabilidade (manual §5.1)."""
    system: StructuralSystem
    confidence: float                 # 0.0 a 1.0
    routing: SystemRouting
    signals: List[str] = field(default_factory=list)
    pendencias: List[str] = field(default_factory=list)


# ── Padroes de deteccao por TEXTO (manual §5.1, regra 1) ────────────────────

_MASONRY_PATTERNS = [
    re.compile(r"\bALVENARIA\s+ESTRUTURAL\b", re.IGNORECASE),
    re.compile(r"\bBLOCO\s+ESTRUTURAL\b", re.IGNORECASE),
    re.compile(r"\bBLOCO\s+DE\s+CONCRETO\s+ESTRUTURAL\b", re.IGNORECASE),
    re.compile(r"\bFAMILIA\s+(?:29|39|44)\b", re.IGNORECASE),  # modulacao
    re.compile(r"\bVERGA\b", re.IGNORECASE),
    re.compile(r"\bCONTRAVERGA\b", re.IGNORECASE),
    re.compile(r"\bGRAUTE\b", re.IGNORECASE),
]

_STEEL_PATTERNS = [
    re.compile(r"\bW\s?\d{3}\s?[xX]\s?\d+(?:[.,]\d+)?\b"),     # W310x38.7
    re.compile(r"\bHP\s?\d{3}\b"),
    re.compile(r"\bCS\s?\d{3}\b"),                              # perfil soldado
    re.compile(r"\bVS\s?\d{3}\b"),
    re.compile(r"\bPERFIL\s+MET[AÁ]LIC", re.IGNORECASE),
    re.compile(r"\bESTRUTURA\s+MET[AÁ]LICA\b", re.IGNORECASE),
    re.compile(r"\bSTEEL\s*DECK\b", re.IGNORECASE),
    re.compile(r"\bASTM\s+A\d{2,3}\b", re.IGNORECASE),
]

_LIGHT_FRAME_PATTERNS = [
    re.compile(r"\bSTEEL\s*FRAME\b", re.IGNORECASE),
    re.compile(r"\bWOOD\s*FRAME\b", re.IGNORECASE),
    re.compile(r"\bLIGHT\s*STEEL\b", re.IGNORECASE),
    re.compile(r"\bOSB\b"),
    re.compile(r"\bDRYWALL\s+ESTRUTURAL\b", re.IGNORECASE),
]

_HEAVY_PATTERNS = [
    re.compile(r"\bPROTENDID[AO]\b", re.IGNORECASE),
    re.compile(r"\bCORDOALHA\b", re.IGNORECASE),
    re.compile(r"\bESTACA\s+H[EÉ]LICE\b", re.IGNORECASE),
    re.compile(r"\bTUBUL[AÃ]O\b", re.IGNORECASE),
    re.compile(r"\bPAREDE\s+DIAFRAGMA\b", re.IGNORECASE),
    re.compile(r"\bBARRAGEM\b", re.IGNORECASE),
    re.compile(r"\bESTAIAD[AO]\b", re.IGNORECASE),
    re.compile(r"\bOAE\b"),
]

_PRECAST_PATTERNS = [
    re.compile(r"\bVIGOTA\b", re.IGNORECASE),
    re.compile(r"\bTRELI[CÇ]ADA\b", re.IGNORECASE),
    re.compile(r"\bALVEOLAR\b", re.IGNORECASE),
    re.compile(r"\bPR[EÉ][\s-]?MOLDAD[AO]\b", re.IGNORECASE),
    re.compile(r"\bLAJOTA\b", re.IGNORECASE),
]

_CONCRETE_PATTERNS = [
    re.compile(r"\bfck\b", re.IGNORECASE),
    re.compile(r"\bCONCRETO\s+ARMADO\b", re.IGNORECASE),
    re.compile(r"\bC\s?(?:25|30|35|40|50)\b"),
    re.compile(r"\bARMADURA\b", re.IGNORECASE),
]


def _count_hits(texts: Sequence[str], patterns: List[re.Pattern]) -> int:
    return sum(1 for t in texts for p in patterns if p.search(t))


def detect_structural_system(
    texts: Sequence[str],
    n_pillars: int = 0,
    n_beams: int = 0,
    n_slabs: int = 0,
    n_bearing_walls: int = 0,
    construction_type: Optional[ConstructionType] = None,
) -> StructuralSystemResult:
    """Detecta o sistema estrutural por texto + geometria (manual §5.1).

    `texts`: conteudo textual do desenho (TextEntity.content).
    Contagens geometricas vem da classificacao de elementos quando
    disponiveis; zeros = sem informacao geometrica ainda (passo zero
    pode rodar so com texto e ser refinado depois).
    """
    signals: List[str] = []
    pendencias: List[str] = []

    heavy = _count_hits(texts, _HEAVY_PATTERNS)
    masonry = _count_hits(texts, _MASONRY_PATTERNS)
    steel = _count_hits(texts, _STEEL_PATTERNS)
    light = _count_hits(texts, _LIGHT_FRAME_PATTERNS)
    precast = _count_hits(texts, _PRECAST_PATTERNS)
    concrete = _count_hits(texts, _CONCRETE_PATTERNS)

    # OAE/contencao do classificador de obra conta como sinal pesado
    if construction_type in (
        ConstructionType.INFRASTRUCTURE_OAE,
    ):
        heavy += 3
        signals.append("ConstructionType=OAE reforcado como sistema pesado")

    # Ordem de precedencia: pesado > light frame > alvenaria > metalica
    # > pre-moldado > concreto armado. Pesado primeiro: presenca de
    # protensao/fundacao profunda bloqueia mesmo havendo concreto.
    if heavy >= 2:
        signals.append(f"{heavy} sinais de construcao pesada/infra")
        return StructuralSystemResult(
            system=StructuralSystem.PESADO_INFRA,
            confidence=min(1.0, 0.5 + 0.15 * heavy),
            routing=ROUTING_BY_SYSTEM[StructuralSystem.PESADO_INFRA],
            signals=signals,
            pendencias=[
                "Sistema pesado/infraestrutura detectado — fora do escopo "
                "automatico (manual §5.1/§19.1); revisao de engenharia."
            ],
        )

    if light >= 2:
        signals.append(f"{light} sinais de wood/steel frame")
        return StructuralSystemResult(
            system=StructuralSystem.WOOD_STEEL_FRAME,
            confidence=min(1.0, 0.5 + 0.2 * light),
            routing=ROUTING_BY_SYSTEM[StructuralSystem.WOOD_STEEL_FRAME],
            signals=signals,
            pendencias=[
                "Wood/steel frame: nao ha concreto estrutural a escorar "
                "(manual §5.1) — fora de escopo."
            ],
        )

    # Alvenaria estrutural: texto OU geometria (paredes portantes sem
    # pilares — manual §5.1, regra 2 de deteccao por geometria).
    masonry_geom = n_bearing_walls > 0 and n_pillars == 0 and n_slabs > 0
    if masonry >= 2 or (masonry >= 1 and masonry_geom) or (
        masonry_geom and n_bearing_walls >= 4
    ):
        if masonry:
            signals.append(f"{masonry} sinais textuais de alvenaria estrutural")
        if masonry_geom:
            signals.append(
                f"geometria: {n_bearing_walls} paredes portantes sem pilares"
            )
        return StructuralSystemResult(
            system=StructuralSystem.ALVENARIA_ESTRUTURAL,
            confidence=min(1.0, 0.45 + 0.15 * masonry + (0.2 if masonry_geom else 0.0)),
            routing=ROUTING_BY_SYSTEM[StructuralSystem.ALVENARIA_ESTRUTURAL],
            signals=signals,
            pendencias=[
                "Alvenaria estrutural: fluxo parcial — escorar somente a "
                "laje, guias/barrotes a <= 5 cm da alvenaria (manual §11.2); "
                "sem escoramento de vigas."
            ],
        )

    if steel >= 2 and steel > concrete:
        signals.append(f"{steel} sinais de estrutura metalica")
        return StructuralSystemResult(
            system=StructuralSystem.ESTRUTURA_METALICA,
            confidence=min(1.0, 0.5 + 0.12 * steel),
            routing=ROUTING_BY_SYSTEM[StructuralSystem.ESTRUTURA_METALICA],
            signals=signals,
            pendencias=[
                "Estrutura metalica/steel deck: em geral dispensa "
                "escoramento de laje (autoportante ate o vao do fabricante); "
                "rota de caso especial com revisao obrigatoria (manual §5.1/§7)."
            ],
        )

    if precast >= 2 and precast > concrete:
        signals.append(f"{precast} sinais de pre-moldado")
        return StructuralSystemResult(
            system=StructuralSystem.PRE_MOLDADO,
            confidence=min(1.0, 0.5 + 0.12 * precast),
            routing=ROUTING_BY_SYSTEM[StructuralSystem.PRE_MOLDADO],
            signals=signals,
            pendencias=[
                "Pre-moldado: fluxo da secao 7.1 (guias perpendiculares as "
                "vigotas, linha de contraflecha; vao maximo e dado do "
                "fabricante — nao inventar)."
            ],
        )

    has_concrete_geometry = n_pillars > 0 and (n_beams > 0 or n_slabs > 0)
    if concrete >= 1 or has_concrete_geometry:
        if concrete:
            signals.append(f"{concrete} sinais textuais de concreto armado")
        if has_concrete_geometry:
            signals.append(
                f"geometria: {n_pillars} pilares, {n_beams} vigas, "
                f"{n_slabs} lajes"
            )
        confidence = min(1.0, 0.4 + 0.1 * concrete + (0.3 if has_concrete_geometry else 0.0))
        # Regra 3 da §5.1: fallback geometrico sem texto -> pendencia
        if concrete == 0:
            pendencias.append(
                "Sistema assumido como concreto armado pelo fallback "
                "geometrico (pilares + vigas/lajes) — confirmar com o "
                "projetista (manual §5.1 regra 3)."
            )
        return StructuralSystemResult(
            system=StructuralSystem.CONCRETO_ARMADO,
            confidence=confidence,
            routing=ROUTING_BY_SYSTEM[StructuralSystem.CONCRETO_ARMADO],
            signals=signals,
            pendencias=pendencias,
        )

    return StructuralSystemResult(
        system=StructuralSystem.UNKNOWN,
        confidence=0.0,
        routing=ROUTING_BY_SYSTEM[StructuralSystem.UNKNOWN],
        signals=["nenhum sinal conclusivo de sistema estrutural"],
        pendencias=[
            "Sistema estrutural nao identificado — revisao de engenharia "
            "antes de emitir projeto (manual §5.1)."
        ],
    )
