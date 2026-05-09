"""Tests for geometric rules GEOM-001 through GEOM-004."""
import pytest

from src.rules.verifiers.geom import (
    _verify_column_setback,
    _verify_slab_edge_setback,
    _verify_min_spacing,
    _verify_shore_in_polygon,
)
from tests.rules.conftest import (
    make_beam, make_pillar, make_project, make_shore, make_slab, rect,
)


class TestGeom001ColumnSetback:
    def test_shore_far_from_pillar_no_violation(self):
        project = make_project(
            pillars=[make_pillar(5.0, 5.0)],
            shore_positions=[make_shore(7.0, 5.0)],
        )
        assert _verify_column_setback(project) == []

    def test_shore_too_close_to_pillar(self):
        project = make_project(
            pillars=[make_pillar(5.0, 5.0)],
            shore_positions=[make_shore(5.3, 5.0)],  # ~0.15m from face
        )
        violations = _verify_column_setback(project)
        assert len(violations) == 1
        assert violations[0].severity == "error"
        assert violations[0].rule_id == "GEOM-001"

    def test_shore_exactly_at_boundary(self):
        # Pillar 0.30x0.30 centered at (5,5): face at x=5.15
        # Shore at x=5.85 = 5.15 + 0.70 exactly
        project = make_project(
            pillars=[make_pillar(5.0, 5.0, 0.30, 0.30)],
            shore_positions=[make_shore(5.85, 5.0)],
        )
        assert _verify_column_setback(project) == []

    def test_no_pillars_no_violations(self):
        project = make_project(
            pillars=[],
            shore_positions=[make_shore(1.0, 1.0)],
        )
        assert _verify_column_setback(project) == []


class TestGeom002SlabEdgeSetback:
    def test_shore_well_inside_slab(self):
        slab = make_slab(
            polygon=rect(0, 0, 5, 5),
            shores=[make_shore(2.5, 2.5)],
        )
        project = make_project(slab_panels=[slab])
        assert _verify_slab_edge_setback(project) == []

    def test_shore_too_close_to_edge(self):
        slab = make_slab(
            polygon=rect(0, 0, 5, 5),
            shores=[make_shore(0.05, 2.5)],  # 5cm from edge
        )
        project = make_project(slab_panels=[slab])
        violations = _verify_slab_edge_setback(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "GEOM-002"

    def test_shore_exactly_at_boundary(self):
        slab = make_slab(
            polygon=rect(0, 0, 5, 5),
            shores=[make_shore(0.15, 2.5)],  # exactly 0.15m
        )
        project = make_project(slab_panels=[slab])
        assert _verify_slab_edge_setback(project) == []


class TestGeom003MinSpacing:
    def test_shores_adequately_spaced(self):
        project = make_project(
            shore_positions=[make_shore(0, 0), make_shore(1.0, 0)],
        )
        assert _verify_min_spacing(project) == []

    def test_shores_too_close(self):
        project = make_project(
            shore_positions=[make_shore(0, 0), make_shore(0.2, 0)],
        )
        violations = _verify_min_spacing(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "GEOM-003"

    def test_single_shore_no_violation(self):
        project = make_project(
            shore_positions=[make_shore(0, 0)],
        )
        assert _verify_min_spacing(project) == []


class TestGeom004ShoreInPolygon:
    def test_shore_inside_polygon(self):
        slab = make_slab(
            polygon=rect(0, 0, 5, 5),
            shores=[make_shore(2.5, 2.5)],
        )
        project = make_project(slab_panels=[slab])
        assert _verify_shore_in_polygon(project) == []

    def test_shore_outside_polygon(self):
        slab = make_slab(
            polygon=rect(0, 0, 5, 5),
            shores=[make_shore(6.0, 6.0)],
        )
        project = make_project(slab_panels=[slab])
        violations = _verify_shore_in_polygon(project)
        assert len(violations) == 1
        assert violations[0].rule_id == "GEOM-004"

    def test_shore_on_boundary_accepted(self):
        slab = make_slab(
            polygon=rect(0, 0, 5, 5),
            shores=[make_shore(0.0, 2.5)],  # on boundary
        )
        project = make_project(slab_panels=[slab])
        assert _verify_shore_in_polygon(project) == []
