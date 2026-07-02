"""RuleProject aggregate — wraps pipeline output for rule checking.

RuleProject is a read-only snapshot of everything verifiers need.
The from_pipeline_result adapter extracts data from the existing
PipelineResult + CalculationResult without modifying the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional



class IncompleteDataError(Exception):
    """Raised when pipeline result lacks data required for rule checking."""
    pass


@dataclass(frozen=True)
class SlabPanel:
    polygon: Any  # Shapely Polygon
    thickness_m: float
    area_m2: float
    shores: list  # List of PositionedShore
    label: str = ""
    is_cantilever: bool = False
    # Manual §28: grid completo de VMs (primarias + secundarias) gerado
    # pelo vm_grid_builder. Tipo real: src.engine.vm_grid_builder.VMGrid.
    # None quando o painel nao gerou grid (nervura, cantilever, <2 shores).
    vm_grid: Any = None


@dataclass(frozen=True)
class BeamInfo:
    centerline: list  # List of (x, y) tuples
    width_m: float
    height_m: float
    length_m: float
    shores: list  # List of PositionedShore
    support_positions: list  # List of float
    is_cantilever_start: bool = False
    is_cantilever_end: bool = False
    is_perimeter: bool = False
    label: str = ""
    decision_rule: str = ""
    total_linear_load_kn_m: float = 0.0


@dataclass(frozen=True)
class PillarInfo:
    center_xy: tuple  # (x, y)
    width_m: float
    depth_m: float
    name: str = ""


@dataclass(frozen=True)
class ShorePosition:
    x: float
    y: float
    shore_type: str  # "telescopic" or "tower"
    load_kn: float = 0.0
    utilization: float = 0.0
    model: str = ""
    height_m: float = 0.0


@dataclass(frozen=True)
class LoadParams:
    q_sobrecarga: float
    q_forma: float
    gamma_f: float
    gamma_concreto: float
    pe_direito_m: float


@dataclass(frozen=True)
class ReescoramentoData:
    """Dados opcionais de reescoramento/desforma (manual §26 items 9 e 10).

    Fornecidos pelo engenheiro quando apresentar o projeto ao cliente. Quando
    ausentes, os verificadores DECIDE-001/DECIDE-002 emitem pendencias.

    Campos:
    - fcj_aos_dias_mpa: resistencia caracteristica a compressao do concreto
      na idade prevista para a desforma (MPa). Necessario para calcular o
      fator alfa Doka (manual §23.6).
    - eci_mpa: modulo de elasticidade do concreto na idade da desforma.
    - carga_final_kn_m2: sobrecarga de uso final (kN/m²) do pavimento.
    - carga_estado_construcao_kn_m2: sobrecarga durante construcao das
      lajes superiores (default 1.50 kN/m² - NBR 15696 Anexo C).
    - num_niveis_reescoramento: quantidade de niveis a manter reescorados.
      Quando >= 1, marca projeto como multi-nivel (DECIDE-001).
    - calculista_aprovacao: nome/CREA do calculista que aprovou os
      parametros. Obrigatorio se desforma_dias for menor que o piso.
    """

    fcj_aos_dias_mpa: Optional[float] = None
    eci_mpa: Optional[float] = None
    carga_final_kn_m2: Optional[float] = None
    carga_estado_construcao_kn_m2: float = 1.50
    num_niveis_reescoramento: int = 0
    calculista_aprovacao: str = ""

    def is_complete(self) -> bool:
        """True quando todos os dados criticos para alfa Doka estao presentes."""
        return (
            self.fcj_aos_dias_mpa is not None
            and self.eci_mpa is not None
            and self.carga_final_kn_m2 is not None
            and self.calculista_aprovacao != ""
        )


@dataclass
class RuleProject:
    """Read-only aggregate for rule verification."""
    slab_panels: List[SlabPanel] = field(default_factory=list)
    beams: List[BeamInfo] = field(default_factory=list)
    pillars: List[PillarInfo] = field(default_factory=list)
    shore_positions: List[ShorePosition] = field(default_factory=list)
    load_params: Optional[LoadParams] = None
    total_volume_m3: float = 0.0
    total_shores_weight_kg: float = 0.0
    pe_direito_m: float = 2.80
    # Como a escala coordenada->metros foi determinada (PipelineResult.scale_method):
    # insunits/dimension/range/override = confiavel; text/default = fallback.
    scale_method: str = ""
    # --- Manual §26 items 9 e 10: bloco opcional de reescoramento ---
    reescoramento_data: Optional[ReescoramentoData] = None
    desforma_dias: Optional[int] = None
    desforma_justificativa: str = ""

    @property
    def multi_level(self) -> bool:
        """True se ha mais de 1 nivel de reescoramento previsto."""
        if self.reescoramento_data is None:
            return False
        return self.reescoramento_data.num_niveis_reescoramento >= 1

    @classmethod
    def from_pipeline_result(cls, result: Any) -> "RuleProject":
        """Build RuleProject from PipelineResult.

        Raises IncompleteDataError if calculation data is missing.
        Does NOT substitute defaults — per Hard Rule #5.
        """
        from src.utils.constants import (
            GAMMA_CONCRETO, Q_SOBRECARGA_DEFAULT, Q_FORMA_DEFAULT, GAMMA_F,
        )

        if result.calculation is None:
            raise IncompleteDataError(
                "PipelineResult.calculation is None — pipeline did not "
                "complete the calculation stage."
            )

        calc = result.calculation
        slab_panels = []
        all_shores = []

        for sr in calc.slab_results:
            shores = []
            for s in sr.shores:
                sp = ShorePosition(
                    x=s.x, y=s.y,
                    shore_type=getattr(s, 'shore_type', 'telescopic'),
                    load_kn=s.load_applied_kn,
                    utilization=s.utilization_ratio,
                    model=getattr(s.shore, 'model', '') if hasattr(s, 'shore') else '',
                    height_m=getattr(s, 'height_m', 0.0),
                )
                shores.append(sp)
                all_shores.append(sp)
            slab_panels.append(SlabPanel(
                polygon=sr.polygon,
                thickness_m=sr.thickness_m,
                area_m2=sr.area_m2,
                shores=shores,
                label=getattr(sr, 'label', ''),
                is_cantilever=getattr(sr, 'is_cantilever', False),
                vm_grid=getattr(sr, 'vm_grid', None),
            ))

        beams = []
        for br in calc.beam_results:
            shores = []
            for s in br.shores:
                sp = ShorePosition(
                    x=s.x, y=s.y,
                    shore_type=getattr(s, 'shore_type', 'telescopic'),
                    load_kn=s.load_applied_kn,
                    utilization=s.utilization_ratio,
                    model=getattr(s.shore, 'model', '') if hasattr(s, 'shore') else '',
                    height_m=getattr(s, 'height_m', 0.0),
                )
                shores.append(sp)
                all_shores.append(sp)
            beams.append(BeamInfo(
                centerline=list(br.beam.geometry) if br.beam.geometry else [],
                width_m=br.beam.section_width_m or 0.0,
                height_m=br.beam.section_height_m or 0.0,
                length_m=br.beam.length_m or 0.0,
                shores=shores,
                support_positions=br.support_positions,
                is_cantilever_start=br.is_cantilever_start,
                is_cantilever_end=br.is_cantilever_end,
                is_perimeter=getattr(br, 'is_perimeter', False),
                label=br.beam.name or '',
                decision_rule=getattr(br, 'decision_rule', ''),
                total_linear_load_kn_m=br.total_linear_load_kn_m,
            ))

        # Extract pillars from levels
        pillars = []
        for level in result.levels:
            for elem in level.elements:
                if elem.element_type.value == "pillar":
                    cx = sum(p[0] for p in elem.geometry) / max(len(elem.geometry), 1)
                    cy = sum(p[1] for p in elem.geometry) / max(len(elem.geometry), 1)
                    pillars.append(PillarInfo(
                        center_xy=(cx, cy),
                        width_m=elem.section_width_m or 0.30,
                        depth_m=elem.section_height_m or 0.30,
                        name=elem.name or '',
                    ))

        load_params = LoadParams(
            q_sobrecarga=Q_SOBRECARGA_DEFAULT,
            q_forma=Q_FORMA_DEFAULT,
            gamma_f=GAMMA_F,
            gamma_concreto=GAMMA_CONCRETO,
            pe_direito_m=calc.pe_direito_m,
        )

        total_weight = sum(
            getattr(sr, 'shores_weight_kg', 0.0) for sr in calc.slab_results
        ) + sum(
            getattr(br, 'shores_weight_kg', 0.0) for br in calc.beam_results
        )

        # Bloco opcional de reescoramento (manual §26 items 9 e 10).
        # Quando o pipeline propaga ``result.reescoramento_data`` e/ou
        # ``result.desforma_dias``, eles fluem para o RuleProject; caso
        # contrario ficam None e os verificadores DECIDE-001/002 emitem
        # pendencia.
        reescoramento = getattr(result, "reescoramento_data", None)
        desforma_dias = getattr(result, "desforma_dias", None)
        desforma_just = getattr(result, "desforma_justificativa", "")

        return cls(
            slab_panels=slab_panels,
            beams=beams,
            pillars=pillars,
            shore_positions=all_shores,
            load_params=load_params,
            total_volume_m3=calc.total_volume_m3,
            total_shores_weight_kg=total_weight,
            pe_direito_m=calc.pe_direito_m,
            scale_method=getattr(result, "scale_method", ""),
            reescoramento_data=reescoramento,
            desforma_dias=desforma_dias,
            desforma_justificativa=desforma_just,
        )
