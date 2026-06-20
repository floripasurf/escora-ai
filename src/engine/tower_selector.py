"""Tower vs telescopic shore decision engine and tower selection.

Decision criteria (NBR 15696 + real Orguel/Mecanor practice):
- Height > 4.5m → tower required (ESC450 max limit)
- Load > 20 kN/point → tower recommended
- Ribbed/thick slab ≥ 30cm → tower with distribution beam
- Height > 12m OR span > 15m → heavy cimbramento

Real locadora insight (Orguel, calibrated on 12 real projects):
- Beams → ALWAYS tower with VM distribution (TORRE_VIGA + VM130/VM80)
  measured: TORRE_VIGA dominates in 8/8 analyzed Orguel beam plans
- Slabs → tower grid when area ≥ 40m² or thick ≥ 20cm, else shores
  (Orguel uses TORRE_LAJE for open continuous slab areas)
- Small cover slabs (<50m² total) → shores only (no towers)

Shore models: ESC310 (2.00-3.10m), ESC450 (3.00-4.50m)
VM130 lengths: 155, 205, 255, 310, 360, 410cm
"""

import json
import math
import logging
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
from src.models.shore import (
    ShoreCatalogEntry, TowerCatalogEntry, DistributionBeamEntry,
    AccessoryCatalogEntry, SupportType,
)
from src.engine.inventory import InventoryAvailability, in_stock

logger = logging.getLogger(__name__)

# Decision thresholds
MAX_TELESCOPIC_HEIGHT_M = 4.5       # ESC450 max height
CIMBRAMENTO_HEIGHT_M = 12.0         # Above this → heavy cimbramento
# Orguel rule 16 (manual): viga interna > 10 m exige somente torres.
# (Era 15 m antes da calibração com locadora — 2026-04-16.)
CIMBRAMENTO_SPAN_M = 10.0
# Intermediate band 6-10 m: prefer 1 central tower + telescopic shores at ends.
BEAM_INTERMEDIATE_SPAN_MIN_M = 6.0
BEAM_INTERMEDIATE_SPAN_MAX_M = 10.0
# Tower fraction for 6-10 m vigas: low so that only ~1 central tower is placed.
BEAM_INTERMEDIATE_TOWER_FRACTION = 0.20
# Rule 16 (viga externa / beiral) — se dentro desses limites, escoras apenas.
PERIMETER_BEAM_MAX_WIDTH_M = 0.30
PERIMETER_BEAM_MAX_HEIGHT_M = 0.60
PERIMETER_BEAM_MAX_LENGTH_M = 3.0
# Envelope leve para viga INTERNA (manual §26 item 7 / §10.2).
# Se qualquer um dos limites for ultrapassado (OR), escala para torres.
BEAM_INTERNAL_MAX_WIDTH_M = 0.40
BEAM_INTERNAL_MAX_HEIGHT_M = 0.70
HEAVY_SLAB_THICKNESS_M = 0.30       # Above this → tower with dist. beam

# Orguel-calibrated slab tower triggers (from 12-project analysis 2026-04-07)
SLAB_TOWER_AREA_M2 = 40.0           # ≥40m² panel → tower grid
SLAB_TOWER_THICKNESS_M = 0.20       # ≥20cm slab → tower grid

# Orguel-measured mixed tower fractions (16,046 entities from 11 Orguel projects):
# Beams: 26.6% towers at intersections → use 0.27
# Slabs: 20.8% towers → use 0.18 (thick) / 0.18 (large)
# NOTE: BEAM_TOWER_FRACTION is a metadata/reporting value — beam MIXED
# placement is structural (intersection + endpoints + gap-fill), not
# fraction-based. But it should match reality for accurate reporting.
BEAM_TOWER_FRACTION = 0.27
SLAB_TOWER_FRACTION_THICK = 0.18
SLAB_TOWER_FRACTION_LARGE = 0.18

# Tower grid spacing for mixed mode (m) — Orguel measured: 2.55m consistent
MIXED_TOWER_GRID_SPACING = 2.55

# Cobertura torre-first (gold standard §28.8 item 10, projetos 35412/97661):
# vigas de cobertura apoiadas em TORRES a 1.25-1.65 m centro-a-centro, com
# VM130-360 entre torres; escoras telescopicas apenas complementares.
COBERTURA_TOWER_SPACING_RANGE_M = (1.25, 1.65)

# NBR 15696 safety factor for shore load combinations
SHORE_SAFETY_FACTOR = 1.4


def load_tower_catalog(catalog_path: Optional[str] = None) -> Tuple[
    List[TowerCatalogEntry], List[DistributionBeamEntry],
    List[AccessoryCatalogEntry],
]:
    """Load tower, distribution beam and accessory catalog from JSON."""
    if catalog_path is None:
        catalog_path = str(
            Path(__file__).parent.parent.parent / "data" / "catalogs" / "shoring_towers.json"
        )

    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    towers = [TowerCatalogEntry(**t) for t in data.get("towers", [])]
    beams = [DistributionBeamEntry(**b) for b in data.get("distribution_beams", [])]
    accessories = [AccessoryCatalogEntry(**a) for a in data.get("accessories", [])]
    return towers, beams, accessories


def decide_support_type(
    required_height_m: float,
    load_per_point_kn: float,
    slab_thickness_m: float = 0.12,
    span_m: float = 0.0,
    slab_type: str = "solid",
    element_type: str = "slab",
    slab_area_m2: float = 0.0,
    shore_catalog: Optional[List[ShoreCatalogEntry]] = None,
    mode: Literal["price", "inventory"] = "price",
    inventory: Optional[InventoryAvailability] = None,
    is_perimeter: bool = False,
    beam_width_m: float = 0.0,
    beam_height_m: float = 0.0,
) -> Tuple[SupportType, float, List[str], str]:
    """Decide between telescopic shore, tower, or mixed support.

    Mixed support (MIXED) replicates real Orguel practice where beams use
    29-44% towers at critical points and slabs use 13-22% towers scattered
    in a wider grid, with telescopic shores filling the rest.

    ----------------------------------------------------------------------
    MAPEAMENTO CADEIA DE DECISAO DO MANUAL §9 (13 perguntas):
    ----------------------------------------------------------------------
    Q1 (H >= 4.50 m?)                         -> rule-1-altura
                                                  Condicional ao catalogo
                                                  (extended shores >4.50m).
    Q2 (H <= 3.50 m, sem excepcionalidade?)   -> rule-0-baixo-pe-direito
                                                  Manual §8 atualizado em
                                                  2026-05-27 (era 3.10).
    Q3 (Carga > capacidade derateada?)         -> rule-1b-carga
                                                  Aplica fator de seguranca
                                                  SHORE_SAFETY_FACTOR (1.4).
    Q4 (Sem torres em estoque + altura ok?)    -> rule-sem-estoque-torre
                                                  Modo "inventory".
    Q5 (Viga externa fora dos limites?)        -> rule-16-externa
                                                  envelope 30 x 60 cm, 3 m.
    Q6 (Viga interna > 10 m OU > 40 cm larg
        OU > 70 cm alt?)                       -> rule-16c-viga-grande
                                                  cobertura via span_m.
    Q7 (Viga interna 6-10 m, ate 40 x 70 cm?)  -> rule-16b-viga-media
                                                  ~1 torre central.
    Q8 (Viga interna ate 6 m, ate 40 x 70 cm?) -> rule-5-viga-mista
                                                  (laje >=15cm ou span>6m).
                                                  Quando nao satisfeito,
                                                  cai para rule-default.
    Q9 (Viga com laje >=15cm ou vao>6m?)       -> rule-5-viga-mista
                                                  (mesma regra de Q8).
    Q10 (Laje >= 20 cm?)                       -> rule-4-laje-espessa
                                                  Manual §9.
    Q11 (Painel laje >= 40 m²?)                -> rule-5-laje-grande
                                                  Manual §9.
    Q12 (Laje nervurada >= 25 cm?)             -> rule-6-nervurada
                                                  Subset Mecaner.
    Q13 (Nenhuma das regras acima?)            -> rule-default-telescopic
                                                  Manual §9 default.
    ----------------------------------------------------------------------

    Returns (support_type, tower_fraction, reasons, decision_rule):
      tower_fraction: 0.0 = all telescopic, 1.0 = all tower, 0 < x < 1 = mixed
      decision_rule: stable short slug identifying which rule fired
    """
    reasons: List[str] = []

    inventory_no_towers = False
    if mode == "inventory" and inventory is not None:
        inventory_no_towers = not any(
            in_stock(inventory, model_id)
            for model_id in inventory.items
            if model_id.startswith("TWR-")
        )

    # Q1: H >= 4.50 m?  →  Torre obrigatoria (manual §9).
    # Rule 1: Height exceeds telescopic limit.
    # Manual §8 / §13.1 (revisado 2026-05-27): bloqueio acima de 4.50 m e
    # CONDICIONAL ao catalogo da locadora. Se houver modelo de escora
    # telescopica estendida (>4.50 m) cadastrada E habilitada, a regra 1
    # nao dispara; o engine cai em Rule 1b para verificar capacidade.
    # Placeholders desabilitados (enabled=False ou available=False) sao
    # ignorados.
    catalog_max_telescopic_m = MAX_TELESCOPIC_HEIGHT_M
    if shore_catalog:
        for shore in shore_catalog:
            if not getattr(shore, "available", True):
                continue
            if not getattr(shore, "enabled", True):
                continue
            shore_max = getattr(shore, "height_max_m", None)
            if shore_max is not None and shore_max > catalog_max_telescopic_m:
                catalog_max_telescopic_m = shore_max

    if required_height_m > catalog_max_telescopic_m:
        reasons.append(
            f"Altura {required_height_m:.1f}m > {catalog_max_telescopic_m:.2f}m "
            f"(limite maximo das escoras cadastradas)"
        )
        return SupportType.TOWER, 1.0, reasons, "rule-1-altura"

    if (
        required_height_m > MAX_TELESCOPIC_HEIGHT_M
        and catalog_max_telescopic_m > MAX_TELESCOPIC_HEIGHT_M
    ):
        reasons.append(
            f"FAIXA ALTA: altura {required_height_m:.2f}m acima de "
            f"{MAX_TELESCOPIC_HEIGHT_M}m exige escora estendida; verificar "
            f"contraventamento e base ampliada (manual §8 nota)"
        )

    # Q2: H <= 3.50 m, sem condicao excepcional?  →  100% escora (manual §9).
    # Rule 0: Low ceiling height — escora telescopica padrao.
    # Manual §8 (revisado): faixa de pe-direito ate 3.50 m e padrao para
    # escoras simples (era 3.10 m antes; ajustado em 2026-05-27 conforme
    # NBR 15696 §4.2 e manual Orguel p.9).
    # Mesmo se a estimativa de carga por ponto parecer alta, o engine pode
    # reduzir o espacamento — torres nao sao necessarias nesta faixa.
    # Esta regra DEVE disparar antes de Rule 1b para evitar escalada
    # falsa de torre por estimativas de carga agressivas em vigas.
    LOW_HEIGHT_TELESCOPIC_MAX_M = 3.50  # manual §8 (era 3.10)
    if required_height_m <= LOW_HEIGHT_TELESCOPIC_MAX_M:
        reasons.append(
            f"Pé-direito {required_height_m:.2f}m ≤ {LOW_HEIGHT_TELESCOPIC_MAX_M}m: "
            f"escora telescópica adequada (manual §8, "
            f"espaçamento reduzido compensa cargas maiores)"
        )
        return SupportType.TELESCOPIC, 0.0, reasons, "rule-0-baixo-pe-direito"

    # Rule 0b: faixa intermediaria 3.50-4.00 m — escora telescopica ainda
    # eh viavel (ESC3000-4500), mas com alerta. Torre facultativa.
    if required_height_m < 4.00:
        reasons.append(
            f"Pé-direito {required_height_m:.2f}m na faixa 3.50-4.00m: "
            f"ESC3000-4500 viavel, torre facultativa por carga/geometria "
            f"(manual §8)"
        )

    # Rule 0c: faixa alta 4.00-4.50 m — torre facultativa, escora ainda valida
    if 4.00 <= required_height_m <= MAX_TELESCOPIC_HEIGHT_M:
        reasons.append(
            f"Pé-direito {required_height_m:.2f}m na faixa 4.00-4.50m: "
            f"torres/andaimes FACULTATIVOS; emitir alerta de faixa alta "
            f"(manual §8)"
        )

    # Q3: Carga majorada por ponto supera capacidade derateada de TODAS
    #     as escoras compativeis?  →  Torre (manual §9).
    # Rule 1b: Load-based derating check.
    # Only relevant for heights > 3.50m where shore capacity is limited.
    if shore_catalog and load_per_point_kn > 0:
        best_cap_kn = 0.0
        for shore in shore_catalog:
            eff = shore.effective_capacity(required_height_m)
            if eff > best_cap_kn:
                best_cap_kn = eff
        required_with_sf = load_per_point_kn * SHORE_SAFETY_FACTOR
        if best_cap_kn > 0 and best_cap_kn < required_with_sf:
            reasons.append(
                f"carga {load_per_point_kn:.1f} kN "
                f"(× SF {SHORE_SAFETY_FACTOR} = {required_with_sf:.1f} kN) > "
                f"capacidade derateada máxima {best_cap_kn:.1f} kN "
                f"para altura {required_height_m:.2f} m"
            )
            return SupportType.TOWER, 1.0, reasons, "rule-1b-carga"

    # Q4: Sem torres em estoque e altura/carga permitem escora?  →  Escora
    #     telescopica (manual §9).
    if inventory_no_towers:
        reasons.append(
            f"Sem torres em estoque ({inventory.locadora}) — usando escora telescópica"
        )
        return SupportType.TELESCOPIC, 0.0, reasons, "rule-sem-estoque-torre"

    # Q5: Viga externa fora dos limites de escora simples?  →  Torre/estaiamento.
    # Rule 16 externa: viga perimetral pequena usa só escora+cruzeta.
    if (
        element_type == "beam"
        and is_perimeter
        and 0 < beam_width_m <= PERIMETER_BEAM_MAX_WIDTH_M
        and 0 < beam_height_m < PERIMETER_BEAM_MAX_HEIGHT_M
        and 0 < span_m <= PERIMETER_BEAM_MAX_LENGTH_M
    ):
        reasons.append(
            f"Viga externa pequena (b={beam_width_m*100:.0f}cm, "
            f"h={beam_height_m*100:.0f}cm, L={span_m:.1f}m): escora+cruzeta apenas "
            f"(regra 16-externa)"
        )
        return SupportType.TELESCOPIC, 0.0, reasons, "rule-16-externa"

    # Q6: Viga interna > 10 m OU >40 cm larg OU >70 cm alt?  →  Torres.
    # Manual §26 item 7 (2026-05-28): envelope leve definido por OR;
    # qualquer estouro escala para sistema com torres.
    if element_type == "beam" and not is_perimeter:
        excede_envelope = (
            span_m > CIMBRAMENTO_SPAN_M
            or beam_width_m > BEAM_INTERNAL_MAX_WIDTH_M
            or beam_height_m > BEAM_INTERNAL_MAX_HEIGHT_M
        )
        if excede_envelope:
            partes = []
            if span_m > CIMBRAMENTO_SPAN_M:
                partes.append(f"L={span_m:.1f}m > {CIMBRAMENTO_SPAN_M}m")
            if beam_width_m > BEAM_INTERNAL_MAX_WIDTH_M:
                partes.append(
                    f"b={beam_width_m*100:.0f}cm > "
                    f"{BEAM_INTERNAL_MAX_WIDTH_M*100:.0f}cm"
                )
            if beam_height_m > BEAM_INTERNAL_MAX_HEIGHT_M:
                partes.append(
                    f"h={beam_height_m*100:.0f}cm > "
                    f"{BEAM_INTERNAL_MAX_HEIGHT_M*100:.0f}cm"
                )
            reasons.append(
                f"Viga interna fora do envelope leve "
                f"({'; '.join(partes)}): torres/sistema especial "
                f"(manual §26 item 7)"
            )
            return SupportType.TOWER, 1.0, reasons, "rule-16c-viga-grande"
    # Rule 2 (fallback nao-viga): span > CIMBRAMENTO_SPAN_M ainda escala torre
    if span_m > CIMBRAMENTO_SPAN_M:
        reasons.append(
            f"Vão {span_m:.1f}m > {CIMBRAMENTO_SPAN_M}m "
            f"(requer cimbramento com torres)"
        )
        return SupportType.TOWER, 1.0, reasons, "rule-16c-viga-grande"

    # --- MIXED SUPPORT RULES (Orguel-calibrated) ---
    # Real Orguel projects show BOTH towers and telescopic on the same element.
    # Beams: 29-44% towers (at pillar intersections), rest telescopic.
    # Slabs: 13-22% towers (wider grid), rest telescopic.

    # Q7: Viga interna 6-10 m, ate 40 x 70 cm?  →  Misto: escoras + torre central.
    # Rule 16b: Viga interna 6-10 m → 1 torre central + escoras
    if (
        element_type == "beam"
        and BEAM_INTERMEDIATE_SPAN_MIN_M < span_m <= BEAM_INTERMEDIATE_SPAN_MAX_M
    ):
        fraction = BEAM_INTERMEDIATE_TOWER_FRACTION
        reasons.append(
            f"Viga interna vão {span_m:.1f}m (6-10m): ~1 torre central + "
            f"escoras nas extremidades (regra 16b)"
        )
        return SupportType.MIXED, fraction, reasons, "rule-16b-viga-media"

    # Q8/Q9: Viga ate 6m com cruzetas, OU viga com laje >=15cm ou vao>6m?
    #        →  Misto (cruzetas + escoras).
    # Rule 3: Beam with moderate load or span → mixed ~35% towers
    if element_type == "beam":
        # Beams with slab ≥ 15cm or span > 6m benefit from mixed support
        if slab_thickness_m >= 0.15 or span_m > 6.0:
            fraction = BEAM_TOWER_FRACTION
            reasons.append(
                f"Viga mista: {fraction:.0%} torres em pontos críticos + "
                f"escoras telescópicas (padrão Orguel medido: 29-44%)"
            )
            return SupportType.MIXED, fraction, reasons, "rule-5-viga-mista"

    # Q10: Laje >= 20 cm?  →  Misto (excecao em pe-direito baixo, ja tratado em Q2).
    # Rule 4: Heavy/thick slab (≥20cm) → mixed ~18% towers
    if slab_thickness_m >= SLAB_TOWER_THICKNESS_M:
        fraction = SLAB_TOWER_FRACTION_THICK
        reasons.append(
            f"Laje {slab_thickness_m*100:.0f}cm ≥ {SLAB_TOWER_THICKNESS_M*100:.0f}cm — "
            f"misto {fraction:.0%} torres + escoras (Orguel medido: 13-22%)"
        )
        return SupportType.MIXED, fraction, reasons, "rule-4-laje-espessa"

    # Q11: Painel de laje >= 40 m²?  →  Misto (excecao em pe-direito baixo).
    # Rule 5: Large slab panel → mixed ~15% towers
    if slab_area_m2 >= SLAB_TOWER_AREA_M2:
        fraction = SLAB_TOWER_FRACTION_LARGE
        reasons.append(
            f"Painel de laje {slab_area_m2:.0f}m² ≥ {SLAB_TOWER_AREA_M2:.0f}m² — "
            f"misto {fraction:.0%} torres em grid largo (Orguel medido: 13-22%)"
        )
        return SupportType.MIXED, fraction, reasons, "rule-5-laje-grande"

    # Q12: Laje nervurada >= 25 cm?  →  Misto ou Mecaner, com revisao.
    # Rule 6: Ribbed slab ≥ 25cm → mixed 20% towers
    if slab_type == "ribbed" and slab_thickness_m > 0.25:
        fraction = 0.20
        reasons.append(
            f"Laje nervurada h={slab_thickness_m*100:.0f}cm — "
            f"misto {fraction:.0%} torres (peso de forma elevado)"
        )
        return SupportType.MIXED, fraction, reasons, "rule-6-nervurada"

    # Q13: Nenhuma regra acionada  →  Escora telescopica (default manual §9).
    # Default: telescopic shore (ESC2000-3100 or ESC3000-4500 by height)
    reasons.append(
        f"Escora telescópica adequada "
        f"(h={required_height_m:.1f}m, laje {slab_thickness_m*100:.0f}cm)"
    )
    return SupportType.TELESCOPIC, 0.0, reasons, "rule-default-telescopic"


def select_tower(
    towers: List[TowerCatalogEntry],
    required_height_m: float,
    required_capacity_kn: float,
    mode: Literal["price", "inventory"] = "price",
    inventory: Optional[InventoryAvailability] = None,
    warnings: Optional[List[str]] = None,
) -> Optional[TowerCatalogEntry]:
    """Select the most economical tower that meets height and load requirements.

    Uses effective_capacity(height) for derating by height (T1.4).
    mode='inventory': prefer towers in stock; fall back to price-min if none.
    """
    compatible = [
        t for t in towers
        if t.max_height_m >= required_height_m
        and t.effective_capacity(required_height_m) >= required_capacity_kn
    ]

    if not compatible:
        compatible = [
            t for t in towers
            if t.effective_capacity(required_height_m) >= required_capacity_kn
        ]

    if not compatible:
        return None

    if mode == "inventory" and inventory is not None:
        in_stock_items = [t for t in compatible if in_stock(inventory, t.id)]
        if in_stock_items:
            return min(
                in_stock_items,
                key=lambda t: t.total_price_brl(required_height_m),
            )
        chosen = min(
            compatible, key=lambda t: t.total_price_brl(required_height_m),
        )
        logger.warning(f"Sem estoque {inventory.locadora}: usando torre {chosen.id}")
        if warnings is not None:
            warnings.append(
                f"Estoque insuficiente em {inventory.locadora}: torre '{chosen.id}' "
                "usada sem confirmacao de estoque (verifique disponibilidade)."
            )
        return chosen

    return min(compatible, key=lambda t: t.total_price_brl(required_height_m))



# Deflection limits by span (manual p.45-50)
DEFLECTION_LIMITS = [
    (2.00, 400),
    (2.50, 415),
    (2.75, 423),
    (3.00, 429),
]


def _max_deflection_ratio(span_m: float) -> float:
    """Return L/ratio for the given span (interpolated from manual table)."""
    if span_m <= DEFLECTION_LIMITS[0][0]:
        return DEFLECTION_LIMITS[0][1]
    if span_m >= DEFLECTION_LIMITS[-1][0]:
        return DEFLECTION_LIMITS[-1][1]
    for (l0, r0), (l1, r1) in zip(DEFLECTION_LIMITS, DEFLECTION_LIMITS[1:]):
        if l0 <= span_m <= l1:
            t = (span_m - l0) / (l1 - l0)
            return r0 + t * (r1 - r0)
    return DEFLECTION_LIMITS[-1][1]


def _passes_deflection_check(beam: 'DistributionBeamEntry', span_m: float, load_kn_m: float) -> bool:
    """Check if beam passes deflection limit (manual p.45-50).

    L_max(deflection) = ∛(384·EI / (5·q·f_max)) where f_max = L/ratio.
    For simply-supported beam: δ_max = 5·q·L⁴ / (384·EI).
    Check: δ_max ≤ L/ratio.
    """
    if beam.EI_knm2 is None or beam.EI_knm2 <= 0:
        return True  # No EI data → skip deflection check (backward compat)
    if span_m <= 0 or load_kn_m <= 0:
        return True
    ratio = _max_deflection_ratio(span_m)
    f_max = span_m / ratio
    delta = 5.0 * load_kn_m * span_m ** 4 / (384.0 * beam.EI_knm2)
    return delta <= f_max


def select_distribution_beam(
    beams: List[DistributionBeamEntry],
    span_m: float,
    load_kn_m: float,
    mode: Literal["price", "inventory"] = "price",
    inventory: Optional[InventoryAvailability] = None,
    n_supports: int = 2,
    warnings: Optional[List[str]] = None,
) -> Optional[DistributionBeamEntry]:
    """Select distribution beam that can span between towers/shores.

    Criteria (dual check — manual p.45-50):
    1. Max span ≥ required span
    2. Moment capacity ≥ M_max = q·L²/8 (biapoiada) or q·L²/10 (3+ apoios)
    3. Deflection ≤ L/ratio (when EI_knm2 is available)
    4. Minimum cost per meter

    Args:
        n_supports: number of supports on the VM. When ≥ 3 (continuous beam),
            uses q·L²/10 instead of q·L²/8 (+25% effective capacity).

    Orguel B1: `available=False` entries (ALU14/ALU20/H20) são ofertas
    técnicas. Modo preço: entram normalmente; modo inventário: são
    sempre filtradas (locadora só sugere o que tem em estoque).
    """
    # T1.3: bônus hiperestático 25% para VMs com 3+ apoios
    divisor = 10.0 if n_supports >= 3 else 8.0
    m_required = load_kn_m * span_m ** 2 / divisor

    candidates = beams if mode == "price" else [b for b in beams if b.available]

    compatible = [
        b for b in candidates
        if b.max_span_m >= span_m
        and b.moment_capacity_knm >= m_required
        and _passes_deflection_check(b, span_m, load_kn_m)
    ]

    if not compatible:
        # Fallback: select by moment capacity only (skip deflection)
        compatible = [
            b for b in candidates
            if b.moment_capacity_knm >= m_required
        ]

    if not compatible:
        return None

    if mode == "inventory" and inventory is not None:
        in_stock_items = [b for b in compatible if in_stock(inventory, b.id)]
        if in_stock_items:
            return min(in_stock_items, key=lambda b: b.price_per_m_brl)
        chosen = min(compatible, key=lambda b: b.price_per_m_brl)
        logger.warning(f"Sem estoque {inventory.locadora}: usando viga {chosen.id}")
        if warnings is not None:
            warnings.append(
                f"Estoque insuficiente em {inventory.locadora}: viga '{chosen.id}' "
                "usada sem confirmacao de estoque (verifique disponibilidade)."
            )
        return chosen

    return min(compatible, key=lambda b: b.price_per_m_brl)



def calculate_tower_grid(
    area_width_m: float,
    area_height_m: float,
    tower: TowerCatalogEntry,
    total_load_kn: float,
    max_spacing_m: float = 3.0,
) -> Tuple[int, int, float, float]:
    """Calculate tower grid dimensions for a given area.

    Spacing is limited by:
    - Tower capacity (load per tower ≤ tower capacity)
    - Distribution beam span (can't exceed beam max_span)
    - Maximum practical spacing (typically 2-3m for towers)

    Returns: (nx, ny, spacing_x, spacing_y)
    """
    # Calculate minimum towers needed by capacity
    min_towers = math.ceil(total_load_kn / tower.load_capacity_kn)
    min_towers = max(min_towers, 4)  # Minimum 2x2 grid

    # Start with max spacing and reduce if needed
    nx = max(2, math.ceil(area_width_m / max_spacing_m) + 1)
    ny = max(2, math.ceil(area_height_m / max_spacing_m) + 1)

    # Ensure enough towers for load
    while nx * ny < min_towers:
        if area_width_m / nx > area_height_m / ny:
            nx += 1
        else:
            ny += 1

    spacing_x = area_width_m / max(nx - 1, 1)
    spacing_y = area_height_m / max(ny - 1, 1)

    # Verify load per tower
    load_per_tower = total_load_kn / (nx * ny)
    if load_per_tower > tower.load_capacity_kn:
        # Need more towers
        factor = math.sqrt(load_per_tower / tower.load_capacity_kn)
        nx = math.ceil(nx * factor)
        ny = math.ceil(ny * factor)
        spacing_x = area_width_m / max(nx - 1, 1)
        spacing_y = area_height_m / max(ny - 1, 1)

    return nx, ny, spacing_x, spacing_y


# Cruzetas-per-shore ratio measured from Orguel SJC stock (lajes only):
# (371 + 5735) cruzetas / ~24,500 ESC units in active rotation ≈ 0.25
ORGUEL_CRUZETA_RATIO_TELESCOPIC = 0.25
# Orguel rule (Q5, manual): viga — 1 conjunto escora+cruzeta a cada 0.80 m
CRUZETA_VIGA_SPACING_M = 0.80
CRUZETAS_PER_TOWER_FACE = 1
TOWER_FACES = 4


def count_cruzetas_viga(
    beam_results,
    spacing_m: Optional[float] = None,
) -> Dict[str, int]:
    """Cruzetas for beams: 1 per `spacing_m` of beam length.

    Locadora rule (Q5): "Em vigas, o conjunto escora+cruzeta é distribuído
    a cada 80 cm sob a viga" — so for a 6m beam we need ceil(6/0.80) = 8
    cruzetas, NOT the 0.25 ratio (which applies only to lajes).

    `spacing_m` defaults to CRUZETA_VIGA_SPACING_M (0.80, DOCX §10.3); o
    perfil de metodologia da locadora (§28.9, `passo_sob_viga_m`) pode
    informar outro passo — gold standard Orguel 0.50-0.65 (§28.8 item 7).

    Tower-supported beams are excluded — towers already carry 4 cruzetas/tower.
    """
    step = spacing_m if spacing_m and spacing_m > 0 else CRUZETA_VIGA_SPACING_M
    out: Dict[str, int] = {}
    for br in beam_results:
        selected = getattr(br, "selected_shore", None)
        if selected is None:
            continue
        sid = selected.id
        if sid.startswith("TWR-"):
            continue
        length_m = getattr(getattr(br, "beam", None), "length_m", 0.0) or 0.0
        if length_m <= 0:
            continue
        out[sid] = out.get(sid, 0) + math.ceil(length_m / step)
    return out


def count_cruzetas_laje(slab_telescopic_counts: Dict[str, int]) -> Dict[str, int]:
    """Cruzetas for slabs: apply Orguel-calibrated 25% ratio."""
    return {
        sid: round(n * ORGUEL_CRUZETA_RATIO_TELESCOPIC)
        for sid, n in slab_telescopic_counts.items()
    }


def compute_cruzeta_bom(
    accessories: List[AccessoryCatalogEntry],
    beam_cruzeta_counts: Dict[str, int],
    slab_cruzeta_counts: Dict[str, int],
    tower_count: int,
) -> List[Tuple[AccessoryCatalogEntry, int]]:
    """Return (accessory, qty) pairs ready for the BOM.

    Args:
        accessories: full accessory catalog (filters internally to cruzetas).
        beam_cruzeta_counts: {shore_id: cruzeta_qty} already computed via
            `count_cruzetas_viga` (0.80 m rule per beam length).
        slab_cruzeta_counts: {shore_id: cruzeta_qty} already computed via
            `count_cruzetas_laje` (0.25 ratio per telescopic shore).
        tower_count: total number of towers in the project.
    """
    out: List[Tuple[AccessoryCatalogEntry, int]] = []
    for acc in accessories:
        if acc.category != "cruzeta":
            continue
        qty = 0
        for sid in acc.associated_model_ids:
            qty += beam_cruzeta_counts.get(sid, 0)
            qty += slab_cruzeta_counts.get(sid, 0)
        if any(t.startswith("TWR-") for t in acc.associated_model_ids):
            qty += tower_count * TOWER_FACES * CRUZETAS_PER_TOWER_FACE
        if qty > 0:
            out.append((acc, qty))
    return out
