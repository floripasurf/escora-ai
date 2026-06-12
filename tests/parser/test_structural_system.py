"""Testes do classificador de sistema estrutural — manual §5.1 (pendência 28)."""

from src.parser.construction_classifier import ConstructionType
from src.parser.structural_system import (
    StructuralSystem,
    SystemRouting,
    detect_structural_system,
)


class TestConcretoArmado:
    def test_texto_fck_e_geometria(self):
        r = detect_structural_system(
            ["fck = 30 MPa", "V1 19x60", "PAVIMENTO TIPO"],
            n_pillars=12, n_beams=20, n_slabs=6,
        )
        assert r.system == StructuralSystem.CONCRETO_ARMADO
        assert r.routing == SystemRouting.FULL
        assert r.confidence > 0.5

    def test_fallback_geometrico_gera_pendencia(self):
        """Regra 3 da §5.1: pilares+vigas+lajes sem texto -> assumir
        concreto armado COM pendência de confirmação."""
        r = detect_structural_system([], n_pillars=8, n_beams=14, n_slabs=4)
        assert r.system == StructuralSystem.CONCRETO_ARMADO
        assert r.pendencias, "fallback geométrico deve registrar pendência"


class TestAlvenariaEstrutural:
    def test_texto(self):
        r = detect_structural_system(
            ["ALVENARIA ESTRUTURAL", "BLOCO ESTRUTURAL 14x19x29", "GRAUTE"],
        )
        assert r.system == StructuralSystem.ALVENARIA_ESTRUTURAL
        assert r.routing == SystemRouting.PARTIAL

    def test_geometria_paredes_sem_pilares(self):
        r = detect_structural_system(
            [], n_pillars=0, n_slabs=4, n_bearing_walls=10,
        )
        assert r.system == StructuralSystem.ALVENARIA_ESTRUTURAL


class TestEstruturaMetalica:
    def test_perfis_w(self):
        r = detect_structural_system(
            ["W310x38.7", "W460x52", "STEEL DECK MF-75"],
        )
        assert r.system == StructuralSystem.ESTRUTURA_METALICA
        assert r.routing == SystemRouting.SPECIAL_REVIEW

    def test_concreto_prevalece_sobre_um_perfil_isolado(self):
        """Um perfil metálico isolado num projeto de concreto armado não
        muda o sistema (ex.: viga metálica de reforço)."""
        r = detect_structural_system(
            ["W310x38.7", "fck = 30 MPa", "CONCRETO ARMADO", "ARMADURA"],
            n_pillars=10, n_beams=18, n_slabs=5,
        )
        assert r.system == StructuralSystem.CONCRETO_ARMADO


class TestPreMoldado:
    def test_vigotas(self):
        r = detect_structural_system(["LAJE TRELIÇADA", "VIGOTA H8", "LAJOTA"])
        assert r.system == StructuralSystem.PRE_MOLDADO
        assert r.routing == SystemRouting.PARTIAL


class TestPesadoInfra:
    def test_protendido_bloqueia(self):
        r = detect_structural_system(
            ["LAJE PROTENDIDA", "CORDOALHA CP-190", "fck = 35"],
            n_pillars=10, n_beams=5, n_slabs=3,
        )
        assert r.system == StructuralSystem.PESADO_INFRA
        assert r.routing == SystemRouting.BLOCKED

    def test_oae_do_construction_type(self):
        r = detect_structural_system(
            ["TABULEIRO", "fck = 40"],
            construction_type=ConstructionType.INFRASTRUCTURE_OAE,
        )
        assert r.system == StructuralSystem.PESADO_INFRA

    def test_fundacao_profunda(self):
        r = detect_structural_system(
            ["ESTACA HÉLICE CONTÍNUA D=40", "PAREDE DIAFRAGMA"],
        )
        assert r.system == StructuralSystem.PESADO_INFRA


class TestWoodSteelFrame:
    def test_bloqueia(self):
        r = detect_structural_system(["STEEL FRAME", "PAINEL OSB 11.1mm"])
        assert r.system == StructuralSystem.WOOD_STEEL_FRAME
        assert r.routing == SystemRouting.BLOCKED


class TestUnknown:
    def test_sem_sinais(self):
        r = detect_structural_system(["PLANTA DE SITUAÇÃO"])
        assert r.system == StructuralSystem.UNKNOWN
        assert r.routing == SystemRouting.SPECIAL_REVIEW
        assert r.pendencias
