"""Tests: slab VM rails must not cross pillars.

Bug observed in production (2026-04-16): o desenho dos trilhos em laje
binava todas as escoras por Y a cada 0.5m e traçava uma linha da escora
mais à esquerda até a mais à direita. Com a densificação C2 colocando
escoras nos lados de cada pilar, o trilho passava POR CIMA do pilar.

Fix: conectar apenas torres consecutivas da mesma linha, com segmento
interrompido quando o gap entre torres ultrapassa 1.5× o grid
(indicando pilar no meio).
"""

import ezdxf
import pytest
from shapely.geometry import box

from api.services.pipeline_service import _generate_output_dxf
from src.engine.grid_distributor import PillarExclusion
from src.models.calculation_models import CalculationResult, SlabShoringResult
from src.models.shore import (
    PositionedShore, ShoreCatalogEntry, SupportType, TowerCatalogEntry,
)


def _shore_entry(sid="ESC310"):
    return ShoreCatalogEntry(
        id=sid, manufacturer="Mecanor", model=sid,
        type="telescopic", height_min_m=2.0, height_max_m=3.1,
        load_capacity_kn=20.0, weight_kg=15.0,
        tube_external_mm=60.0, tube_internal_mm=48.0,
        base_plate_mm=150.0, price_reference_brl=80.0,
    )


def _tower_entry():
    return TowerCatalogEntry(
        id="TWR-TA150", manufacturer="Orguel", model="TA-150",
        load_capacity_kn=120.0, module_height_m=1.5, base_dimension_m=1.54,
        max_height_m=20.0, weight_per_module_kg=38.0, includes_bracing=True,
        price_per_module_brl=15.0,
    )


def _mixed_slab_with_pillar_at_center():
    """Laje 8×4 com pilar em (4,2). Torres posicionadas em grid nos lados
    do pilar: (1,2), (7,2) — cross-pillar scenario. Rail entre elas não
    pode cruzar o pilar."""
    shore = _shore_entry()
    tower = _tower_entry()
    polygon = box(0, 0, 8, 4)

    # Duas torres na mesma linha (y=2), uma em cada lado do pilar (4,2)
    towers = [
        PositionedShore(x=1.0, y=2.0, shore=shore,
                        load_applied_kn=20.0, utilization_ratio=0.7,
                        support_type=SupportType.TOWER, tower=tower),
        PositionedShore(x=7.0, y=2.0, shore=shore,
                        load_applied_kn=20.0, utilization_ratio=0.7,
                        support_type=SupportType.TOWER, tower=tower),
    ]
    # Algumas telescópicas espalhadas
    telescopic = [
        PositionedShore(x=1.0, y=0.5, shore=shore,
                        load_applied_kn=8.0, utilization_ratio=0.4),
        PositionedShore(x=7.0, y=0.5, shore=shore,
                        load_applied_kn=8.0, utilization_ratio=0.4),
    ]
    # Exclusão do pilar centralizado em (4, 2) com 60×60cm + margem
    exclusion = PillarExclusion(cx=4.0, cy=2.0, width_m=0.60, depth_m=0.60)

    slab = SlabShoringResult(
        polygon=polygon, thickness_m=0.12, thickness_is_default=True,
        area_m2=32.0, is_cantilever=False, total_load_kn=200.0,
        shores=towers + telescopic, grid_nx=2, grid_ny=2,
        spacing_x_m=6.0, spacing_y_m=1.5,
        selected_shore=shore, exclusions=[exclusion],
    )
    return slab


def _calc_with_slab(slab):
    return CalculationResult(
        beam_results=[], slab_results=[slab], shore_catalog_used=[],
        total_shores=len(slab.shores), total_load_kn=slab.total_load_kn,
        pe_direito_m=2.80,
    )


@pytest.fixture
def empty_input_dxf(tmp_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "0"})
    path = str(tmp_path / "input.dxf")
    doc.saveas(path)
    return path


def _segment_crosses_exclusion(x0, x1, y, exclusion: PillarExclusion) -> bool:
    """Verifica se o segmento horizontal (x0,y)-(x1,y) cruza a exclusão.

    Segmento é horizontal: só precisamos checar se y está em Y-range do
    pilar E se o X-range do pilar intersecta [x0,x1].
    """
    if y < exclusion.min_y or y > exclusion.max_y:
        return False
    xlo, xhi = min(x0, x1), max(x0, x1)
    return xhi >= exclusion.min_x and xlo <= exclusion.max_x


class TestSlabRailsAvoidPillars:
    def test_rail_does_not_cross_pillar_exclusion(
        self, empty_input_dxf, tmp_path,
    ):
        """Trilho horizontal não pode atravessar exclusão do pilar."""
        slab = _mixed_slab_with_pillar_at_center()
        out = str(tmp_path / "out.dxf")
        _generate_output_dxf(empty_input_dxf, _calc_with_slab(slab), out)

        doc = ezdxf.readfile(out)
        msp = doc.modelspace()
        # Trilhos de laje: layer começa com "VM" E é relativo à Laje
        rails = [
            e for e in msp.query("LINE")
            if e.dxf.layer.startswith("VM")
            and e.dxf.layer.endswith("_Laje")
        ]

        exclusion = slab.exclusions[0]
        for line in rails:
            s, e = line.dxf.start, line.dxf.end
            if abs(s.y - e.y) > 1e-3:
                continue  # not horizontal rail
            assert not _segment_crosses_exclusion(
                s.x, e.x, s.y, exclusion
            ), (
                f"Trilho ({s.x:.2f},{s.y:.2f})→({e.x:.2f},{e.y:.2f}) cruza "
                f"o pilar [x={exclusion.min_x:.2f}..{exclusion.max_x:.2f}, "
                f"y={exclusion.min_y:.2f}..{exclusion.max_y:.2f}]"
            )
