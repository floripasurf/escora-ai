"""LOAD-003: amplificação 10/8 na escora do apoio central (Orguel p.109 r.14).

O engine (beam_calculator) aplica 1.25x na escora mais próxima do apoio
central para vigas com exatamente 3 apoios. O verificador exige razão >= 1.20
sobre a mediana das demais escoras.
"""
from src.rules.verifiers.load import _verify_hyperestaticity

from tests.rules.conftest import make_beam, make_project, make_shore


def _beam_3_supports(central_load: float, other_load: float = 8.0):
    # Viga horizontal de 8 m com apoios em 0 / 4 / 8 e 5 escoras.
    shores = [
        make_shore(0.5, 0.0, load_kn=other_load),
        make_shore(2.0, 0.0, load_kn=other_load),
        make_shore(4.0, 0.0, load_kn=central_load),  # apoio central
        make_shore(6.0, 0.0, load_kn=other_load),
        make_shore(7.5, 0.0, load_kn=other_load),
    ]
    return make_beam(
        centerline=[(0, 0), (8, 0)],
        length_m=8.0,
        shores=shores,
        support_positions=[0.0, 4.0, 8.0],
    )


def test_amplified_central_shore_passes():
    beam = _beam_3_supports(central_load=10.0)  # 1.25 × 8.0
    project = make_project(beams=[beam])
    assert _verify_hyperestaticity(project) == []


def test_missing_amplification_flags_violation():
    beam = _beam_3_supports(central_load=8.0)  # sem acréscimo
    project = make_project(beams=[beam])
    violations = _verify_hyperestaticity(project)
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "LOAD-003"
    assert v.severity == "error"
    assert v.limit_value == 1.20
    assert v.location == (4.0, 0.0)


def test_two_supports_out_of_scope():
    beam = make_beam(
        centerline=[(0, 0), (5, 0)],
        shores=[make_shore(1.0, 0.0), make_shore(4.0, 0.0),
                make_shore(2.5, 0.0)],
        support_positions=[0.0, 5.0],
    )
    assert _verify_hyperestaticity(make_project(beams=[beam])) == []


def test_four_supports_out_of_scope():
    # Engine só amplifica com exatamente 3 apoios — >=4 fica fora do escopo.
    beam = _beam_3_supports(central_load=8.0)
    beam = make_beam(
        centerline=beam.centerline,
        length_m=beam.length_m,
        shores=beam.shores,
        support_positions=[0.0, 2.5, 5.5, 8.0],
    )
    assert _verify_hyperestaticity(make_project(beams=[beam])) == []


def test_vertical_beam_projection():
    # Viga no eixo Y — projeção das escoras no eixo deve funcionar igual.
    shores = [
        make_shore(0.0, 0.5, load_kn=8.0),
        make_shore(0.0, 4.0, load_kn=8.0),  # apoio central SEM acréscimo
        make_shore(0.0, 7.5, load_kn=8.0),
    ]
    beam = make_beam(
        centerline=[(0, 0), (0, 8)],
        length_m=8.0,
        shores=shores,
        support_positions=[0.0, 4.0, 8.0],
    )
    violations = _verify_hyperestaticity(make_project(beams=[beam]))
    assert len(violations) == 1
    assert violations[0].location == (0.0, 4.0)
