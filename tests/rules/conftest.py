"""Shared test helpers for rule tests.

Provides factory functions to create synthetic RuleProject instances
with minimal data for targeted rule testing.
"""
import pytest
from shapely.geometry import Polygon, box

from src.rules.project import (
    BeamInfo, LoadParams, PillarInfo, RuleProject, ShorePosition, SlabPanel,
)


def rect(x: float, y: float, w: float, h: float) -> Polygon:
    """Create a rectangular Shapely polygon."""
    return box(x, y, x + w, y + h)


def make_project(
    slab_panels=None,
    beams=None,
    pillars=None,
    shore_positions=None,
    load_params=None,
    pe_direito_m=2.80,
    total_volume_m3=0.0,
    total_shores_weight_kg=0.0,
) -> RuleProject:
    """Create a RuleProject with defaults for testing."""
    if load_params is None:
        load_params = LoadParams(
            q_sobrecarga=2.0,
            q_forma=0.50,
            gamma_f=1.4,
            gamma_concreto=25.0,
            pe_direito_m=pe_direito_m,
        )
    return RuleProject(
        slab_panels=slab_panels or [],
        beams=beams or [],
        pillars=pillars or [],
        shore_positions=shore_positions or [],
        load_params=load_params,
        pe_direito_m=pe_direito_m,
        total_volume_m3=total_volume_m3,
        total_shores_weight_kg=total_shores_weight_kg,
    )


def make_shore(x: float, y: float, shore_type: str = "telescopic",
               load_kn: float = 10.0, utilization: float = 0.5,
               model: str = "ESC310") -> ShorePosition:
    """Create a ShorePosition for testing."""
    return ShorePosition(
        x=x, y=y, shore_type=shore_type,
        load_kn=load_kn, utilization=utilization, model=model,
    )


def make_slab(polygon=None, thickness_m=0.12, shores=None,
              label="L1") -> SlabPanel:
    """Create a SlabPanel for testing."""
    if polygon is None:
        polygon = rect(0, 0, 5, 5)
    return SlabPanel(
        polygon=polygon,
        thickness_m=thickness_m,
        area_m2=polygon.area,
        shores=shores or [],
        label=label,
    )


def make_pillar(cx: float, cy: float, width_m: float = 0.30,
                depth_m: float = 0.30, name: str = "P1") -> PillarInfo:
    """Create a PillarInfo for testing."""
    return PillarInfo(
        center_xy=(cx, cy), width_m=width_m,
        depth_m=depth_m, name=name,
    )


def make_beam(centerline=None, width_m=0.20, height_m=0.50,
              length_m=5.0, shores=None, support_positions=None,
              is_perimeter=False, label="V1",
              is_cantilever_start=False, is_cantilever_end=False) -> BeamInfo:
    """Create a BeamInfo for testing."""
    if centerline is None:
        centerline = [(0, 0), (length_m, 0)]
    return BeamInfo(
        centerline=centerline,
        width_m=width_m,
        height_m=height_m,
        length_m=length_m,
        shores=shores or [],
        support_positions=support_positions or [],
        is_perimeter=is_perimeter,
        label=label,
        is_cantilever_start=is_cantilever_start,
        is_cantilever_end=is_cantilever_end,
    )
