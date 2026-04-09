"""Extract and normalize report data from CalculationResult."""

from dataclasses import dataclass, field
from typing import List, Optional
from collections import Counter

from src.models.calculation_models import CalculationResult
from src.utils.constants import ESPESSURA_DEFAULT


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
class ReportData:
    project_name: str
    date: str
    summary: SummaryData
    beam_rows: List[BeamRow] = field(default_factory=list)
    slab_rows: List[SlabRow] = field(default_factory=list)
    bom_rows: List[BomRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


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

    # Accessories — cruzetas derived from telescopic + tower counts
    try:
        from src.engine.tower_selector import compute_cruzeta_bom, load_tower_catalog
        _, _, accessories = load_tower_catalog()
        telescopic_counts = {
            sid: c for sid, (_s, c) in shore_counts.items()
            if not sid.startswith("TWR-")
        }
        tower_count = sum(
            c for sid, (_s, c) in shore_counts.items()
            if sid.startswith("TWR-")
        )
        for acc, qty in compute_cruzeta_bom(accessories, telescopic_counts, tower_count):
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

    # Warnings — merge warnings + validation_errors
    all_warnings = list(calc.warnings)
    for err in calc.validation_errors:
        all_warnings.append(f"ERRO: {err}")

    return ReportData(
        project_name=metadata.project_name,
        date=metadata.date,
        summary=summary,
        beam_rows=beam_rows,
        slab_rows=slab_rows,
        bom_rows=bom_rows,
        warnings=all_warnings,
    )
