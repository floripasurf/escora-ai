"""Tests: capitel densification shores must be TELESCOPIC (never TOWER).

Bug observed in production (2026-04-16): in MIXED slab support (towers +
telescopic), the capitel densification (Orguel Q6) added dense shores
around pillars (0.70-1.50m ring). But because the MIXED tower-swap ran
AFTER densification and picked evenly-spaced indices, some of those
capitel shores were converted to TOWER. Result: torres grudadas nos
pilares em pé-direito baixo — contrary to Orguel practice.

Fix: capitel ring shores must stay TELESCOPIC. Either run densification
AFTER the MIXED swap, OR exclude capitel indices from the swap set.

NOTA (2026-05-28): Apos manual §8, faixa de escora padrao foi ampliada
de 3.10m para 3.50m. Fixture recalibrado para pe=3.80m + slab=0.25m +
geometria 15x12 (180m²) - garante MIXED com tower swap no pipeline.
"""
import math

from src.engine.tower_selector import SupportType
from src.models.pipeline_models import ClassifiedElement, ElementType
from src.pipeline.stage_calculate import run_calculation


def _beam(x1, y1, x2, y2, width=0.14, height=0.40):
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return ClassifiedElement(
        element_type=ElementType.BEAM,
        geometry=[(x1, y1), (x2, y2)],
        score_geometric=0.85, score_textual=0.0, score_final=0.75,
        section_width_m=width, section_height_m=height, length_m=length,
    )


def _pillar(cx, cy, w=0.20, h=0.40):
    return ClassifiedElement(
        element_type=ElementType.PILLAR,
        geometry=[(cx, cy)],
        score_geometric=0.80, score_textual=0.0, score_final=0.70,
        section_width_m=w, section_height_m=h,
    )


def _large_slab_elements():
    """Painel 15x12 (180m²) com 5 pilares - garante MIXED no pipeline.

    Manual §8 (2026-05-28): pe-direito >3.50m + laje >=20cm + area
    grande dispara rule-4-laje-espessa MIXED e o pipeline executa o
    tower swap completo.
    """
    beams = [
        _beam(0, 0, 15, 0),
        _beam(0, 12, 15, 12),
        _beam(0, 0, 0, 12),
        _beam(15, 0, 15, 12),
    ]
    pillars = [
        _pillar(0, 0), _pillar(15, 0),
        _pillar(0, 12), _pillar(15, 12),
        # Pilar interno para gerar capitel claro no meio
        _pillar(7.5, 6.0),
    ]
    return beams + pillars, [(p.geometry[0][0], p.geometry[0][1]) for p in pillars]


class TestCapitelNeverBecomesTower:
    def test_tower_shores_not_in_capitel_ring(self):
        """No TOWER shore may lie within 1.50m of any pillar."""
        elements, pillar_xy = _large_slab_elements()
        # Manual §8 (2026-05-28): pe=3.80m + laje 25cm + 180m² area
        # forca MIXED com tower swap real no pipeline.
        result = run_calculation(elements, pe_direito_m=3.80,
                                 slab_thickness_m=0.25)

        # Only MIXED slabs exercise the bug; at least one must be MIXED
        mixed_slabs = [
            s for s in result.slab_results
            if any(
                getattr(sh, "support_type", None) == SupportType.TOWER
                for sh in s.shores
            )
        ]
        assert mixed_slabs, (
            "Nenhuma laje MIXED — teste não exerce o bug. "
            "Ajuste a geometria para acionar MIXED."
        )

        for slab in mixed_slabs:
            for shore in slab.shores:
                if getattr(shore, "support_type", None) != SupportType.TOWER:
                    continue
                for px, py in pillar_xy:
                    d = math.hypot(shore.x - px, shore.y - py)
                    assert d > 1.50 - 1e-3, (
                        f"Torre em ({shore.x:.2f},{shore.y:.2f}) está a "
                        f"{d:.2f}m do pilar ({px},{py}) — dentro do anel "
                        f"de capitel (≤1.50m), deveria ser TELESCOPIC."
                    )

    def test_capitel_densification_produces_telescopic_shores(self):
        """Shores in capitel ring (0.70-1.50m) exist and are telescopic."""
        elements, pillar_xy = _large_slab_elements()
        # Manual §8 (2026-05-28): pe=3.80m + laje 25cm + 180m² area
        # forca MIXED com tower swap real no pipeline.
        result = run_calculation(elements, pe_direito_m=3.80,
                                 slab_thickness_m=0.25)

        capitel_shores = 0
        for slab in result.slab_results:
            for shore in slab.shores:
                for px, py in pillar_xy:
                    d = math.hypot(shore.x - px, shore.y - py)
                    if 0.70 - 1e-3 <= d <= 1.50 + 1e-3:
                        capitel_shores += 1
                        assert (
                            getattr(shore, "support_type", None)
                            != SupportType.TOWER
                        ), f"Escora em capitel ({shore.x},{shore.y}) é TOWER"
                        break

        assert capitel_shores > 0, (
            "Nenhuma escora no anel de capitel — densificação C2 não rodou"
        )
