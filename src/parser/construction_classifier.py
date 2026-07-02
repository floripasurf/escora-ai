"""Classify construction type and slab type from DXF content.

Analyzes layers, text annotations, entity patterns, and geometry to determine:
1. Construction type (building, infrastructure/OAE, retaining wall, industrial)
2. Slab type (solid, ribbed/nervurada, waffle/treliçada, prestressed, steel deck)

These classifications determine which normative rules and shoring methods apply.
"""

import re
import logging
from enum import Enum
from typing import List
from dataclasses import dataclass, field
from src.pipeline.stage_parse import (
    TextEntity, SegmentEntity, RectEntity, HatchEntity, DimensionEntity, PolylineEntity,
)

logger = logging.getLogger(__name__)


class ConstructionType(str, Enum):
    """Type of construction project."""
    BUILDING_RESIDENTIAL = "building_residential"
    BUILDING_COMMERCIAL = "building_commercial"
    INDUSTRIAL = "industrial"
    INFRASTRUCTURE_OAE = "infrastructure_oae"  # bridges, viaducts
    RETAINING_WALL = "retaining_wall"
    UNKNOWN = "unknown"


class SlabType(str, Enum):
    """Type of slab detected."""
    SOLID = "solid"              # Laje maciça
    RIBBED = "ribbed"            # Laje nervurada (moldada in-loco)
    WAFFLE = "waffle"            # Laje treliçada (pré-moldada)
    PRESTRESSED = "prestressed"  # Laje protendida
    STEEL_DECK = "steel_deck"    # Steel deck / forma metálica
    UNKNOWN = "unknown"


@dataclass
class NormativeProfile:
    """Normative parameters for a specific construction type."""
    construction_type: ConstructionType
    primary_norms: List[str]
    gamma_f: float = 1.4          # Safety factor (NBR 15696)
    q_sobrecarga: float = 1.5     # Live load kN/m² (NBR 15696)
    gamma_concreto: float = 25.0  # Concrete density kN/m³
    unit_system: str = "m"        # "m" or "mm"
    notes: List[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    """Result of construction and slab type classification."""
    construction_type: ConstructionType
    construction_confidence: float  # 0.0 to 1.0
    slab_type: SlabType
    slab_confidence: float
    normative_profile: NormativeProfile
    signals: List[str]  # Human-readable explanation of classification


# ──────────────────────────────────────────────────────────────
# Normative profiles per construction type
# ──────────────────────────────────────────────────────────────

NORMATIVE_PROFILES = {
    ConstructionType.BUILDING_RESIDENTIAL: NormativeProfile(
        construction_type=ConstructionType.BUILDING_RESIDENTIAL,
        primary_norms=["NBR 15696:2009", "NBR 6118:2023", "NBR 6120:2019"],
        gamma_f=1.4, q_sobrecarga=1.5, gamma_concreto=25.0, unit_system="m",
        notes=["Escoramento padrão para edifícios residenciais"],
    ),
    ConstructionType.BUILDING_COMMERCIAL: NormativeProfile(
        construction_type=ConstructionType.BUILDING_COMMERCIAL,
        primary_norms=["NBR 15696:2009", "NBR 6118:2023", "NBR 6120:2019"],
        gamma_f=1.4, q_sobrecarga=2.0, gamma_concreto=25.0, unit_system="m",
        notes=["Sobrecarga maior para uso comercial (2.0 kN/m²)"],
    ),
    ConstructionType.INDUSTRIAL: NormativeProfile(
        construction_type=ConstructionType.INDUSTRIAL,
        primary_norms=["NBR 15696:2009", "NBR 6118:2023", "NBR 8681:2003"],
        gamma_f=1.4, q_sobrecarga=3.0, gamma_concreto=25.0, unit_system="m",
        notes=["Sobrecarga elevada para industrial (3.0 kN/m²)", "Verificar pontes rolantes"],
    ),
    ConstructionType.INFRASTRUCTURE_OAE: NormativeProfile(
        construction_type=ConstructionType.INFRASTRUCTURE_OAE,
        primary_norms=["NBR 15696:2009", "NBR 7187:2021", "NBR 7188:2013"],
        gamma_f=1.4, q_sobrecarga=5.0, gamma_concreto=25.0, unit_system="mm",
        notes=["Cimbramento de OAE", "Unidade em mm", "Cargas de veículos NBR 7188"],
    ),
    ConstructionType.RETAINING_WALL: NormativeProfile(
        construction_type=ConstructionType.RETAINING_WALL,
        primary_norms=["NBR 15696:2009 Anexo D", "NBR 11682:2009"],
        gamma_f=1.4, q_sobrecarga=1.5, gamma_concreto=25.0, unit_system="m",
        notes=["Pressão lateral: Pb = 12*Vb + 12", "Empuxo de terra: Rankine"],
    ),
    ConstructionType.UNKNOWN: NormativeProfile(
        construction_type=ConstructionType.UNKNOWN,
        primary_norms=["NBR 15696:2009"],
        gamma_f=1.4, q_sobrecarga=1.5, gamma_concreto=25.0, unit_system="m",
    ),
}


# ──────────────────────────────────────────────────────────────
# Detection patterns
# ──────────────────────────────────────────────────────────────

# Infrastructure (OAE) signals
OAE_TEXT_PATTERNS = [
    re.compile(r"\bENCONTRO\s+E\d", re.IGNORECASE),
    re.compile(r"\bTABULEIRO\b", re.IGNORECASE),
    re.compile(r"\bLONGARINA\b", re.IGNORECASE),
    re.compile(r"\bTRANSVERSINA\b", re.IGNORECASE),
    re.compile(r"\bEST(?:ACA)?\.?\s*\d+\+", re.IGNORECASE),  # Estaqueamento
    re.compile(r"\bVIADUTO\b", re.IGNORECASE),
    re.compile(r"\bPONTE\b", re.IGNORECASE),
    re.compile(r"\bAPARELHO\s+DE\s+APOIO\b", re.IGNORECASE),
    re.compile(r"\bJUNTA\s+DE\b", re.IGNORECASE),
    re.compile(r"\bGUARDA[\s-]?RODAS?\b", re.IGNORECASE),
    re.compile(r"\bLAJE\s+DE\s+APROXIMA", re.IGNORECASE),
    re.compile(r"\bDEFENSA\b", re.IGNORECASE),
]

OAE_LAYER_PREFIXES = ["FOR-", "ARM-", "DIM-"]

# Retaining wall signals
WALL_TEXT_PATTERNS = [
    re.compile(r"\bMURO\s+DE\s+(?:ARRIMO|CONTEN)", re.IGNORECASE),
    re.compile(r"\bCONTEN[CÇ][AÃ]O\b", re.IGNORECASE),
    re.compile(r"\bMURO\s+(?:DE\s+)?GRAV", re.IGNORECASE),
    re.compile(r"\bPARED[EÃ]O\b", re.IGNORECASE),
    re.compile(r"\bEMPUXO\b", re.IGNORECASE),
    re.compile(r"\bTIRANTE\b", re.IGNORECASE),
]

# Industrial signals
INDUSTRIAL_TEXT_PATTERNS = [
    re.compile(r"\bGALP[AÃ]O\b", re.IGNORECASE),
    re.compile(r"\bPONTE\s+ROLANTE\b", re.IGNORECASE),
    re.compile(r"\bTRELI[CÇ]A\s+MET", re.IGNORECASE),
    re.compile(r"\bSILO\b", re.IGNORECASE),
    re.compile(r"\bINDUSTRIA", re.IGNORECASE),
]

# Building signals
BUILDING_TEXT_PATTERNS = [
    re.compile(r"\bV\d+\w?\b", re.IGNORECASE),     # V1, V1a, V10
    re.compile(r"\bP\d+\w?\b", re.IGNORECASE),      # P1, p70
    re.compile(r"\bL\d+\w?\b", re.IGNORECASE),      # L1, L10
    re.compile(r"\bPAVIMENTO\b", re.IGNORECASE),
    re.compile(r"\bCOBERTURA\b", re.IGNORECASE),
    re.compile(r"\bSUBSOLO\b", re.IGNORECASE),
    re.compile(r"\bTERRASSO\b", re.IGNORECASE),
    re.compile(r"\bAPARTAMENTO\b", re.IGNORECASE),
    re.compile(r"\bSALA\b", re.IGNORECASE),
]

# Slab type patterns
RIBBED_SLAB_PATTERNS = [
    re.compile(r"\bNERVURADA\b", re.IGNORECASE),
    re.compile(r"\bNERVURA\b", re.IGNORECASE),
    re.compile(r"\bCUBETA\b", re.IGNORECASE),
    re.compile(r"\bLN\s*\d", re.IGNORECASE),
    re.compile(r"\bLAJE\s+NERVURADA\b", re.IGNORECASE),
]

WAFFLE_SLAB_PATTERNS = [
    re.compile(r"\bTRELI[CÇ]ADA\b", re.IGNORECASE),
    re.compile(r"\bPR[EÉ][\s-]?MOLDAD[AO]\b", re.IGNORECASE),
    re.compile(r"\bLAJE\s+TRELI", re.IGNORECASE),
    re.compile(r"\bVIGOTA\b", re.IGNORECASE),
    re.compile(r"\bLAJOTA\b", re.IGNORECASE),
]

PRESTRESSED_SLAB_PATTERNS = [
    re.compile(r"\bPROTENDID[AO]\b", re.IGNORECASE),
    re.compile(r"\bCORDOALHA\b", re.IGNORECASE),
    re.compile(r"\bPROTEN[SÇ][AÃ]O\b", re.IGNORECASE),
    re.compile(r"\bCABO\s+DE\s+PROTENÇÃO", re.IGNORECASE),
]

STEEL_DECK_PATTERNS = [
    re.compile(r"\bSTEEL\s*DECK\b", re.IGNORECASE),
    re.compile(r"\bFORMA\s+MET[AÁ]LICA\b", re.IGNORECASE),
    re.compile(r"\bCOLABORANTE\b", re.IGNORECASE),
]


def _count_pattern_matches(texts: List[TextEntity], patterns: List[re.Pattern]) -> int:
    """Count how many text entities match any of the given patterns."""
    count = 0
    for t in texts:
        for p in patterns:
            if p.search(t.content):
                count += 1
                break  # Count each text entity only once
    return count


def _check_oae_layers(layers: List[str]) -> int:
    """Count layers with OAE-specific prefixes (FOR-, ARM-, DIM-)."""
    count = 0
    for layer in layers:
        for prefix in OAE_LAYER_PREFIXES:
            if layer.upper().startswith(prefix):
                count += 1
                break
    return count


def _check_numeric_layers(layers: List[str]) -> bool:
    """Check if layers follow TQS numeric pattern (1, 2, 3, 22, 27, 42...)."""
    numeric_count = 0
    for layer in layers:
        if layer.strip().isdigit():
            numeric_count += 1
    return numeric_count >= 10  # TQS typically has 30+ numeric layers


def _detect_ribbed_slab_geometry(
    segments: List[SegmentEntity], polylines: List[PolylineEntity],
) -> float:
    """Detect ribbed slab pattern from parallel equally-spaced lines.

    Returns confidence (0.0-1.0) that ribbed slab geometry is present.
    """
    # Group horizontal segments by approximate Y position
    y_positions = sorted(set(
        round(s.y, 2) for s in segments if s.type == "H"
    ))

    if len(y_positions) < 5:
        return 0.0

    # Check for uniform spacing patterns
    spacings = [y_positions[i+1] - y_positions[i] for i in range(len(y_positions) - 1)]

    # Filter spacings in ribbed slab range (0.3m to 0.9m)
    rib_spacings = [s for s in spacings if 0.30 <= s <= 0.90]
    if len(rib_spacings) < 3:
        return 0.0

    # Check uniformity (std dev < 15% of mean)
    mean_spacing = sum(rib_spacings) / len(rib_spacings)
    if mean_spacing == 0:
        return 0.0
    variance = sum((s - mean_spacing) ** 2 for s in rib_spacings) / len(rib_spacings)
    std_dev = variance ** 0.5
    cv = std_dev / mean_spacing  # coefficient of variation

    if cv < 0.05 and len(rib_spacings) >= 5:
        return 0.90  # Very uniform spacing with many lines
    elif cv < 0.10 and len(rib_spacings) >= 4:
        return 0.75
    elif cv < 0.15 and len(rib_spacings) >= 3:
        return 0.60
    return 0.0


def classify_construction(
    texts: List[TextEntity],
    layers: List[str],
    segments: List[SegmentEntity],
    rects: List[RectEntity],
    hatches: List[HatchEntity],
    dimensions: List[DimensionEntity],
    polylines: List[PolylineEntity],
) -> ClassificationResult:
    """Classify construction type and slab type from DXF content.

    Uses a scoring system across multiple signals:
    - Text annotations (strongest signal)
    - Layer naming patterns
    - Entity type distribution (HATCH, DIMENSION, INSERT counts)
    - Geometric patterns (parallel rib lines)
    """
    signals: List[str] = []
    scores = {
        ConstructionType.BUILDING_RESIDENTIAL: 0.0,
        ConstructionType.BUILDING_COMMERCIAL: 0.0,
        ConstructionType.INDUSTRIAL: 0.0,
        ConstructionType.INFRASTRUCTURE_OAE: 0.0,
        ConstructionType.RETAINING_WALL: 0.0,
    }

    # ── Signal 1: Text pattern matching ──
    oae_matches = _count_pattern_matches(texts, OAE_TEXT_PATTERNS)
    wall_matches = _count_pattern_matches(texts, WALL_TEXT_PATTERNS)
    industrial_matches = _count_pattern_matches(texts, INDUSTRIAL_TEXT_PATTERNS)
    building_matches = _count_pattern_matches(texts, BUILDING_TEXT_PATTERNS)

    if oae_matches >= 3:
        scores[ConstructionType.INFRASTRUCTURE_OAE] += 0.40
        signals.append(f"OAE: {oae_matches} textos de infraestrutura")
    elif oae_matches >= 1:
        scores[ConstructionType.INFRASTRUCTURE_OAE] += 0.20
        signals.append(f"OAE: {oae_matches} texto(s) de infraestrutura")

    if wall_matches >= 2:
        scores[ConstructionType.RETAINING_WALL] += 0.40
        signals.append(f"Contenção: {wall_matches} textos de muro/arrimo")
    elif wall_matches >= 1:
        scores[ConstructionType.RETAINING_WALL] += 0.20

    if industrial_matches >= 2:
        scores[ConstructionType.INDUSTRIAL] += 0.40
        signals.append(f"Industrial: {industrial_matches} textos industriais")

    if building_matches >= 5:
        scores[ConstructionType.BUILDING_RESIDENTIAL] += 0.30
        signals.append(f"Edifício: {building_matches} labels V/P/L")
    elif building_matches >= 2:
        scores[ConstructionType.BUILDING_RESIDENTIAL] += 0.15

    # ── Signal 2: Layer patterns ──
    oae_layer_count = _check_oae_layers(layers)
    if oae_layer_count >= 5:
        scores[ConstructionType.INFRASTRUCTURE_OAE] += 0.30
        signals.append(f"OAE: {oae_layer_count} layers FOR-/ARM-/DIM-")

    if _check_numeric_layers(layers):
        scores[ConstructionType.BUILDING_RESIDENTIAL] += 0.20
        signals.append("Edifício: layers numéricos (padrão TQS)")

    # ── Signal 3: Entity distribution ──
    has_many_hatches = len(hatches) >= 10
    has_many_dimensions = len(dimensions) >= 20

    if has_many_hatches and has_many_dimensions:
        scores[ConstructionType.INFRASTRUCTURE_OAE] += 0.15
        signals.append(f"OAE: {len(hatches)} hatches + {len(dimensions)} dimensions")

    if not hatches and not dimensions:
        scores[ConstructionType.BUILDING_RESIDENTIAL] += 0.10
        signals.append("Edifício: sem HATCH/DIMENSION (padrão TQS)")

    # ── Signal 4: Coordinate range (mm vs m) ──
    all_coords = []
    for s in segments[:1000]:  # Sample first 1000
        if s.type == "H":
            all_coords.extend([abs(s.x_min), abs(s.x_max), abs(s.y)])
        else:
            all_coords.extend([abs(s.x), abs(s.y_min), abs(s.y_max)])
    if all_coords:
        max_coord = max(all_coords)
        if max_coord > 1000:  # Likely mm units
            scores[ConstructionType.INFRASTRUCTURE_OAE] += 0.10
            signals.append(f"Coordenadas em mm (max={max_coord:.0f})")

    # ── Determine construction type ──
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score < 0.15:
        best_type = ConstructionType.UNKNOWN
        best_score = 0.0
        signals.append("Tipo de obra não identificado com confiança")

    # Normalize confidence
    construction_confidence = min(1.0, best_score)

    # ── Slab type classification ──
    slab_type = SlabType.UNKNOWN
    slab_confidence = 0.0
    slab_signals: List[str] = []

    # Text-based slab detection
    ribbed_text = _count_pattern_matches(texts, RIBBED_SLAB_PATTERNS)
    waffle_text = _count_pattern_matches(texts, WAFFLE_SLAB_PATTERNS)
    prestressed_text = _count_pattern_matches(texts, PRESTRESSED_SLAB_PATTERNS)
    steel_deck_text = _count_pattern_matches(texts, STEEL_DECK_PATTERNS)

    if ribbed_text >= 1:
        slab_type = SlabType.RIBBED
        slab_confidence = min(0.95, 0.70 + 0.10 * ribbed_text)
        slab_signals.append(f"Laje nervurada: {ribbed_text} menção(ões) no texto")

    if waffle_text >= 1:
        new_confidence = min(0.95, 0.70 + 0.10 * waffle_text)
        if new_confidence > slab_confidence:
            slab_type = SlabType.WAFFLE
            slab_confidence = new_confidence
            slab_signals.append(f"Laje treliçada: {waffle_text} menção(ões) no texto")

    if prestressed_text >= 1:
        new_confidence = min(0.95, 0.75 + 0.10 * prestressed_text)
        if new_confidence > slab_confidence:
            slab_type = SlabType.PRESTRESSED
            slab_confidence = new_confidence
            slab_signals.append(f"Laje protendida: {prestressed_text} menção(ões)")

    if steel_deck_text >= 1:
        new_confidence = min(0.95, 0.75 + 0.10 * steel_deck_text)
        if new_confidence > slab_confidence:
            slab_type = SlabType.STEEL_DECK
            slab_confidence = new_confidence
            slab_signals.append(f"Steel deck: {steel_deck_text} menção(ões)")

    # Geometric-based ribbed slab detection (layer 7 polylines or parallel lines)
    if slab_type == SlabType.UNKNOWN:
        rib_geo_confidence = _detect_ribbed_slab_geometry(segments, polylines)
        if rib_geo_confidence > 0.50:
            slab_type = SlabType.RIBBED
            slab_confidence = rib_geo_confidence
            slab_signals.append(f"Laje nervurada detectada por geometria (confiança={rib_geo_confidence:.0%})")

    # Default to solid slab if building type and no slab type detected
    if slab_type == SlabType.UNKNOWN and best_type in (
        ConstructionType.BUILDING_RESIDENTIAL, ConstructionType.BUILDING_COMMERCIAL,
    ):
        slab_type = SlabType.SOLID
        slab_confidence = 0.50
        slab_signals.append("Laje maciça assumida (sem indicação de tipo especial)")

    signals.extend(slab_signals)

    normative = NORMATIVE_PROFILES.get(best_type, NORMATIVE_PROFILES[ConstructionType.UNKNOWN])

    result = ClassificationResult(
        construction_type=best_type,
        construction_confidence=construction_confidence,
        slab_type=slab_type,
        slab_confidence=slab_confidence,
        normative_profile=normative,
        signals=signals,
    )

    logger.info(
        f"Classification: {best_type.value} ({construction_confidence:.0%}), "
        f"slab={slab_type.value} ({slab_confidence:.0%})"
    )

    return result
