"""Extract and normalize report data from CalculationResult."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict

from src.models.calculation_models import CalculationResult
from src.utils.constants import ESPESSURA_DEFAULT
from src.utils.labels import CATEGORY_DEFAULT, CATEGORY_LABELS_PT


# Aproximação de vigas vazadas (distribution beams) por torre.
# Razão prática medida em projetos Orguel:
# - Vigas (beam): 2 trilhos × (n_towers−1) gaps ⇒ ~1.5/torre
# - Lajes em grid quadrado nx×ny: 2nx(ny−1) ⇒ ~1.3-1.5/torre
# Valor usado: 2.0 (lado conservador para orçamento de peso).
VIGAS_VAZADAS_POR_TORRE = 2.0

# Prefixos para classificação de BOM rows como acessórios.
ACCESSORY_ID_PREFIXES = ("CRZ-", "VD-")
SHORE_TOWER_ID_PREFIX = "TWR-"


@dataclass
class ReportMetadata:
    project_name: str
    date: str
    scale: float
    dxf_filename: str


@dataclass
class SummaryData:
    total_shores: int
    total_load_kn: float
    pe_direito_m: float
    pe_direito_is_default: bool
    slab_thickness_m: float
    thickness_is_default: bool
    beam_count: int
    slab_count: int
    is_valid: bool


@dataclass
class BeamRow:
    name: str
    section: str
    section_width_m: Optional[float]
    section_height_m: Optional[float]
    length_m: float
    load_kn_m: float
    shore_count: int
    spacing_m: float
    shore_model: str
    is_cantilever: bool


@dataclass
class SlabRow:
    panel_id: int
    area_m2: float
    thickness_m: float
    total_load_kn: float
    grid: str
    spacing_x_m: float
    spacing_y_m: float
    shore_model: str
    is_cantilever: bool


@dataclass
class BomRow:
    id: str
    model: str
    manufacturer: str
    quantity: int
    capacity_kn: float
    height_min_m: float
    height_max_m: float
    weight_kg: float
    total_weight_kg: float
    price_brl: float
    total_price_brl: float


@dataclass
class VolumeRow:
    """Linha didática da aba `Volumes` (um painel/elemento por linha)."""
    category: str            # chave: "laje" | "beiral" | ...
    category_label: str      # rótulo PT: "Laje", "Beiral", ...
    element: str             # rótulo completo do painel: "Laje 1 (Quarto 1)"
    area_m2: float
    pe_direito_m: float
    volume_m3: float


@dataclass
class ConsumptionByHeightRow:
    """Linha agregada de consumo de escoramento por (pé-direito, categoria)."""
    pe_direito_m: float            # chave do grupo (arredondado 2 casas)
    area_m2: float                 # Σ áreas dos painéis
    volume_bruto_m3: float         # Σ (area × pe_direito) do grupo
    volume_liquido_m3: float       # bruto − vigas − pilares (pro-rata)
    shores_weight_kg: float        # peso das escoras (telescópicas + torres)
    accessories_weight_kg: float   # cruzetas + vigas vazadas (pro-rata)
    total_weight_kg: float         # shores + accessories
    rate_kg_m3_bruto: float        # total / volume_bruto
    rate_kg_m3_liquido: float      # total / volume_liquido
    rate_kg_m2: float              # total / area
    category_label: str = "Laje"   # rótulo PT da categoria do grupo


@dataclass
class ReportData:
    project_name: str
    date: str
    summary: SummaryData
    beam_rows: List[BeamRow] = field(default_factory=list)
    slab_rows: List[SlabRow] = field(default_factory=list)
    bom_rows: List[BomRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    volume_rows: List[VolumeRow] = field(default_factory=list)
    volume_totals: Dict[str, float] = field(default_factory=dict)
    consumption_rows: List[ConsumptionByHeightRow] = field(default_factory=list)
    consumption_totals: Dict[str, float] = field(default_factory=dict)


def _format_section(width_m: Optional[float], height_m: Optional[float]) -> str:
    if width_m is None or height_m is None:
        return "N/D"
    w_cm = round(width_m * 100)
    h_cm = round(height_m * 100)
    return f"{w_cm}x{h_cm} cm"


def build_report_data(
    calc: CalculationResult,
    metadata: ReportMetadata,
) -> ReportData:
    """Build normalized ReportData from CalculationResult."""

    # Summary — slab thickness from first slab or default
    if calc.slab_results:
        slab_thickness = calc.slab_results[0].thickness_m
        thickness_is_default = calc.slab_results[0].thickness_is_default
    else:
        slab_thickness = ESPESSURA_DEFAULT
        thickness_is_default = True

    summary = SummaryData(
        total_shores=calc.total_shores,
        total_load_kn=calc.total_load_kn,
        pe_direito_m=calc.pe_direito_m,
        pe_direito_is_default=calc.pe_direito_is_default,
        slab_thickness_m=slab_thickness,
        thickness_is_default=thickness_is_default,
        beam_count=len(calc.beam_results),
        slab_count=len(calc.slab_results),
        is_valid=calc.is_valid,
    )

    # Beam rows
    beam_rows = []
    for br in calc.beam_results:
        beam_rows.append(BeamRow(
            name=br.beam.name or "Viga sem nome",
            section=_format_section(br.beam.section_width_m, br.beam.section_height_m),
            section_width_m=br.beam.section_width_m,
            section_height_m=br.beam.section_height_m,
            length_m=br.beam.length_m or 0.0,
            load_kn_m=br.total_linear_load_kn_m,
            shore_count=br.shore_count,
            spacing_m=br.spacing_m,
            shore_model=br.selected_shore.model,
            is_cantilever=br.is_cantilever_start or br.is_cantilever_end,
        ))

    # Slab rows
    slab_rows = []
    for i, sr in enumerate(calc.slab_results):
        slab_rows.append(SlabRow(
            panel_id=i + 1,
            area_m2=sr.area_m2,
            thickness_m=sr.thickness_m,
            total_load_kn=sr.total_load_kn,
            grid=f"{sr.grid_nx}x{sr.grid_ny}",
            spacing_x_m=sr.spacing_x_m,
            spacing_y_m=sr.spacing_y_m,
            shore_model=sr.selected_shore.model if sr.selected_shore else "N/A",
            is_cantilever=sr.is_cantilever,
        ))

    # BOM — aggregate by shore model ID
    shore_counts: dict = {}  # id -> (ShoreCatalogEntry, count)
    for br in calc.beam_results:
        sid = br.selected_shore.id
        if sid not in shore_counts:
            shore_counts[sid] = [br.selected_shore, 0]
        shore_counts[sid][1] += br.shore_count
    for sr in calc.slab_results:
        if sr.selected_shore:
            sid = sr.selected_shore.id
            if sid not in shore_counts:
                shore_counts[sid] = [sr.selected_shore, 0]
            shore_counts[sid][1] += len(sr.shores)

    bom_rows = []
    for sid, (shore, qty) in shore_counts.items():
        bom_rows.append(BomRow(
            id=sid,
            model=shore.model,
            manufacturer=shore.manufacturer,
            quantity=qty,
            capacity_kn=shore.load_capacity_kn,
            height_min_m=shore.height_min_m,
            height_max_m=shore.height_max_m,
            weight_kg=shore.weight_kg,
            total_weight_kg=round(shore.weight_kg * qty, 2),
            price_brl=shore.price_reference_brl,
            total_price_brl=round(shore.price_reference_brl * qty, 2),
        ))

    # Accessories — cruzetas split: vigas (0.80 m rule), lajes (0.25 ratio),
    # torres (4 por torre). See Orguel Q5.
    try:
        from src.engine.tower_selector import (
            compute_cruzeta_bom,
            count_cruzetas_laje,
            count_cruzetas_viga,
            load_tower_catalog,
        )
        _, _, accessories = load_tower_catalog()
        # Slab-only telescopic counts for the 0.25 ratio
        slab_telescopic_counts: Dict[str, int] = {}
        for sr in calc.slab_results:
            for s in sr.shores:
                from src.models.shore import SupportType
                if getattr(s, "support_type", None) == SupportType.TOWER:
                    continue
                sid = s.shore.id
                slab_telescopic_counts[sid] = slab_telescopic_counts.get(sid, 0) + 1
        tower_count = sum(
            c for sid, (_s, c) in shore_counts.items()
            if sid.startswith("TWR-")
        )
        beam_cruzetas = count_cruzetas_viga(calc.beam_results)
        slab_cruzetas = count_cruzetas_laje(slab_telescopic_counts)
        for acc, qty in compute_cruzeta_bom(
            accessories, beam_cruzetas, slab_cruzetas, tower_count,
        ):
            bom_rows.append(BomRow(
                id=acc.id,
                model=acc.model,
                manufacturer=acc.manufacturer,
                quantity=qty,
                capacity_kn=0.0,
                height_min_m=0.0,
                height_max_m=0.0,
                weight_kg=acc.weight_kg,
                total_weight_kg=round(acc.weight_kg * qty, 1),
                price_brl=acc.price_brl,
                total_price_brl=round(acc.price_brl * qty, 2),
            ))
    except Exception:
        pass

    # Accessories — vigas vazadas (distribution beams) por modelo VM*
    # Conta torres com distribution_beam associada × razão prática.
    bom_rows.extend(_build_distribution_beam_bom_rows(calc))

    # Volume breakdown → linhas da aba Volumes
    volume_rows: List[VolumeRow] = []
    for entry in calc.volume_breakdown:
        volume_rows.append(VolumeRow(
            category=entry.category,
            category_label=CATEGORY_LABELS_PT.get(entry.category, entry.category.title()),
            element=entry.label,
            area_m2=entry.area_m2,
            pe_direito_m=entry.pe_direito_m,
            volume_m3=entry.volume_m3,
        ))

    volume_totals: Dict[str, float] = {
        "bruto_m3": calc.slab_volume_gross_m3,
        "vigas_m3": calc.beam_volume_deducted_m3,
        "pilares_m3": calc.pillar_volume_deducted_m3,
        "liquido_m3": calc.total_volume_m3,
    }

    # Consumo por pé-direito (resumo interno de orçamento)
    consumption_rows, consumption_totals = _build_consumption_rows(calc, bom_rows)

    # Warnings — merge warnings + validation_errors + consumption rate checks
    all_warnings = list(calc.warnings)
    for err in calc.validation_errors:
        all_warnings.append(f"ERRO: {err}")
    all_warnings.extend(_consumption_rate_warnings(consumption_rows))

    return ReportData(
        project_name=metadata.project_name,
        date=metadata.date,
        summary=summary,
        beam_rows=beam_rows,
        slab_rows=slab_rows,
        bom_rows=bom_rows,
        warnings=all_warnings,
        volume_rows=volume_rows,
        volume_totals=volume_totals,
        consumption_rows=consumption_rows,
        consumption_totals=consumption_totals,
    )


# ----------------------------------------------------------------------------
# Helpers para consumo por pé-direito e vigas vazadas no BOM
# ----------------------------------------------------------------------------

def _build_distribution_beam_bom_rows(calc: CalculationResult) -> List[BomRow]:
    """Agrega vigas vazadas (distribution_beams) em linhas de BOM.

    Conta torres com `distribution_beam` associado e multiplica por
    `VIGAS_VAZADAS_POR_TORRE` (aproximação de trilhos por torre).
    Peso por unidade = `max_span_m × weight_per_m_kg`.

    Nota: hoje apenas torres de vigas (beam_results) recebem
    `distribution_beam` no pipeline. Torres de lajes ficam fora até o
    pipeline anexar a viga escolhida a elas.
    """
    # id_db -> [DistributionBeamEntry, tower_count]
    db_counts: Dict[str, List] = {}

    def _collect(shore_list):
        for s in shore_list:
            db = getattr(s, "distribution_beam", None)
            if db is None:
                continue
            if getattr(s, "support_type", None) is None:
                continue
            # Só contamos torres (escoras telescópicas não usam viga vazada)
            from src.models.shore import SupportType
            if s.support_type != SupportType.TOWER:
                continue
            entry = db_counts.setdefault(db.id, [db, 0])
            entry[1] += 1

    for br in calc.beam_results:
        _collect(br.shores)
    for sr in calc.slab_results:
        _collect(sr.shores)

    rows: List[BomRow] = []
    for _db_id, (db, tower_count) in db_counts.items():
        qty = int(round(tower_count * VIGAS_VAZADAS_POR_TORRE))
        if qty <= 0:
            continue
        weight_unit = round(db.max_span_m * db.weight_per_m_kg, 2)
        price_unit = round(db.max_span_m * db.price_per_m_brl, 2)
        rows.append(BomRow(
            id=db.id,
            model=db.model,
            manufacturer=db.manufacturer,
            quantity=qty,
            capacity_kn=0.0,
            height_min_m=0.0,
            height_max_m=0.0,
            weight_kg=weight_unit,
            total_weight_kg=round(weight_unit * qty, 2),
            price_brl=price_unit,
            total_price_brl=round(price_unit * qty, 2),
        ))
    return rows


def _is_accessory_bom_row(row: BomRow) -> bool:
    """Classifica a linha como acessório (cruzeta ou viga vazada)."""
    return any(row.id.startswith(p) for p in ACCESSORY_ID_PREFIXES)


def _safe_div(num: float, den: float) -> float:
    if den <= 0:
        return 0.0
    return num / den


# Orguel rule A6 / Q8: taxa kg/m³ esperada 12-16 (faixa usual),
# 8-20 (faixa aceitável). Fora disso, warning.
CONSUMPTION_RATE_USUAL_MIN_KG_M3 = 12.0
CONSUMPTION_RATE_USUAL_MAX_KG_M3 = 16.0
CONSUMPTION_RATE_ACCEPTABLE_MIN_KG_M3 = 8.0
CONSUMPTION_RATE_ACCEPTABLE_MAX_KG_M3 = 20.0


def _consumption_rate_warnings(
    rows: List[ConsumptionByHeightRow],
) -> List[str]:
    """Validate rate_kg_m3_bruto vs Orguel expected ranges.

    Two levels:
    - Critical (rate ∉ [8, 20]): likely wrong inputs (pé-direito, espessura).
    - Soft (rate ∈ [8, 20] but ∉ [12, 16]): outside usual range, review.

    Rates ≤ 0 are skipped (no volume to validate against).
    """
    warnings: List[str] = []
    for r in rows:
        rate = r.rate_kg_m3_bruto
        if rate <= 0:
            continue
        label = f"{r.category_label} @ pé-direito {r.pe_direito_m:.2f} m"
        if (
            rate < CONSUMPTION_RATE_ACCEPTABLE_MIN_KG_M3
            or rate > CONSUMPTION_RATE_ACCEPTABLE_MAX_KG_M3
        ):
            warnings.append(
                f"{label}: taxa {rate:.1f} kg/m³ fora do esperado "
                f"({CONSUMPTION_RATE_ACCEPTABLE_MIN_KG_M3:.0f}-"
                f"{CONSUMPTION_RATE_ACCEPTABLE_MAX_KG_M3:.0f}) "
                "— verificar inputs (pé-direito, espessura, inventário)"
            )
        elif (
            rate < CONSUMPTION_RATE_USUAL_MIN_KG_M3
            or rate > CONSUMPTION_RATE_USUAL_MAX_KG_M3
        ):
            warnings.append(
                f"{label}: taxa {rate:.1f} kg/m³ fora da faixa usual "
                f"({CONSUMPTION_RATE_USUAL_MIN_KG_M3:.0f}-"
                f"{CONSUMPTION_RATE_USUAL_MAX_KG_M3:.0f} kg/m³)"
            )
    return warnings


def _build_consumption_rows(
    calc: CalculationResult,
    bom_rows: List[BomRow],
) -> Tuple[List[ConsumptionByHeightRow], Dict[str, float]]:
    """Agrega consumo (peso) por (pé-direito, categoria).

    Estratégia:
    1. Agrupa `volume_breakdown` por `(round(pe_direito_m, 2), category_label)`
       — soma área, volume bruto e peso das escoras das lajes. O rótulo PT
       vem de `CATEGORY_LABELS_PT` (Laje, Beiral, Balanço, Platibanda, ...).
    2. Soma peso de escoras das vigas no grupo `(calc.pe_direito_m, "Laje")`
       — vigas concretas sustentam lajes, então entram na categoria default.
    3. Volume líquido = bruto − (vigas_global + pilares_global) pro-rata
       pelo volume bruto de cada grupo.
    4. Acessórios (cruzetas + vigas vazadas) pro-rata pelo volume bruto.
    5. Taxas kg/m³ bruto, kg/m³ líquido e kg/m² com guard contra div/0.

    Retorna (rows ordenadas por (pe_direito ASC, category_label ASC), totais).
    """
    default_label = CATEGORY_LABELS_PT.get(CATEGORY_DEFAULT, "Laje")

    # 1. Agrupar entries de volume_breakdown por (pé-direito, categoria)
    groups: Dict[Tuple[float, str], Dict[str, float]] = defaultdict(
        lambda: {"area_m2": 0.0, "volume_bruto_m3": 0.0, "shores_weight_kg": 0.0}
    )
    for entry in calc.volume_breakdown:
        pe_key = round(entry.pe_direito_m, 2)
        label = CATEGORY_LABELS_PT.get(entry.category, entry.category.title())
        g = groups[(pe_key, label)]
        g["area_m2"] += entry.area_m2
        g["volume_bruto_m3"] += entry.volume_m3
        g["shores_weight_kg"] += entry.shores_weight_kg

    # 2. Peso das escoras das vigas → grupo (pe_direito_global, "Laje")
    beam_shores_kg = sum(
        getattr(br, "shores_weight_kg", 0.0) for br in calc.beam_results
    )
    if beam_shores_kg > 0:
        pe_key = round(calc.pe_direito_m, 2)
        groups[(pe_key, default_label)]["shores_weight_kg"] += beam_shores_kg

    # Caso degenerado: nenhum painel e nenhuma viga → retorna vazio
    if not groups:
        return [], {}

    total_bruto = sum(g["volume_bruto_m3"] for g in groups.values())
    deduct_total = calc.beam_volume_deducted_m3 + calc.pillar_volume_deducted_m3

    # Acessórios globais — extraídos do BOM já montado
    accessories_total_kg = sum(
        r.total_weight_kg for r in bom_rows if _is_accessory_bom_row(r)
    )

    # 3 + 4 + 5. Monta linhas, ordenadas por (pe ASC, categoria ASC)
    rows: List[ConsumptionByHeightRow] = []
    for key in sorted(groups.keys(), key=lambda k: (k[0], k[1])):
        pe_key, label = key
        g = groups[key]
        bruto = g["volume_bruto_m3"]
        area = g["area_m2"]
        shores_kg = g["shores_weight_kg"]
        share = _safe_div(bruto, total_bruto) if total_bruto > 0 else 0.0
        liquido = max(bruto - deduct_total * share, 0.0)
        acc_kg = accessories_total_kg * share
        total_kg = shores_kg + acc_kg
        rows.append(ConsumptionByHeightRow(
            pe_direito_m=pe_key,
            area_m2=round(area, 2),
            volume_bruto_m3=round(bruto, 2),
            volume_liquido_m3=round(liquido, 2),
            shores_weight_kg=round(shores_kg, 2),
            accessories_weight_kg=round(acc_kg, 2),
            total_weight_kg=round(total_kg, 2),
            rate_kg_m3_bruto=round(_safe_div(total_kg, bruto), 2),
            rate_kg_m3_liquido=round(_safe_div(total_kg, liquido), 2),
            rate_kg_m2=round(_safe_div(total_kg, area), 2),
            category_label=label,
        ))

    # Totais agregados
    sum_area = sum(r.area_m2 for r in rows)
    sum_bruto = sum(r.volume_bruto_m3 for r in rows)
    sum_liquido = sum(r.volume_liquido_m3 for r in rows)
    sum_shores = sum(r.shores_weight_kg for r in rows)
    sum_acc = sum(r.accessories_weight_kg for r in rows)
    sum_total = sum(r.total_weight_kg for r in rows)

    totals = {
        "area_m2": round(sum_area, 2),
        "volume_bruto_m3": round(sum_bruto, 2),
        "volume_liquido_m3": round(sum_liquido, 2),
        "shores_kg": round(sum_shores, 2),
        "accessories_kg": round(sum_acc, 2),
        "total_kg": round(sum_total, 2),
        "rate_kg_m3_bruto": round(_safe_div(sum_total, sum_bruto), 2),
        "rate_kg_m3_liquido": round(_safe_div(sum_total, sum_liquido), 2),
        "rate_kg_m2": round(_safe_div(sum_total, sum_area), 2),
    }
    return rows, totals
