"""RuleProject aggregate — wraps pipeline output for rule checking.

RuleProject is a read-only snapshot of everything verifiers need.
The from_pipeline_result adapter extracts data from the existing
PipelineResult + CalculationResult without modifying the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from shapely.geometry import Polygon


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

        return cls(
            slab_panels=slab_panels,
            beams=beams,
            pillars=pillars,
            shore_positions=all_shores,
            load_params=load_params,
            total_volume_m3=calc.total_volume_m3,
            total_shores_weight_kg=total_weight,
            pe_direito_m=calc.pe_direito_m,
        )
