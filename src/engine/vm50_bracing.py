"""VM50 bracing BOM — Orguel Q4.

A VM50 tem três usos práticos no canteiro que precisam entrar no BOM
como peças separadas dos trilhos de distribuição:

1. **Travamento lateral de vigas**: barras horizontais que amarram as
   formas laterais da viga, distribuídas a cada 0.80-1.0 m. Usamos
   `VM50_LATERAL_SPACING_M = 0.90 m` (midpoint da faixa informada).

2. **Travamento de pilares**: cada pilar leva um conjunto com 2× VM50
   + 2 barras de ancoragem com porca (amarração das formas do pilar).

3. **Fundo de viga**: 1 conjunto de VM50 por escora com cruzeta (viga
   escorada com telescópicas). Vigas escoradas com torres já têm o
   fundo travado via a própria torre — são excluídas aqui.

Para o BOM final, somamos as 3 categorias em `total_vm50` e reportamos
separadamente `pilar_barras_ancoragem` (peça diferente).
"""

from dataclasses import dataclass
from math import ceil
from typing import Iterable, List

from src.models.calculation_models import BeamShoringResult


# Espaçamento de barras VM50 no travamento lateral da viga.
# Locadora informou faixa 0.80-1.0 m; usamos 0.90 m como valor de projeto.
VM50_LATERAL_SPACING_M = 0.90

# Peças por pilar (Orguel Q4, regra 2).
VM50_PER_PILAR = 2
BARRAS_ANCORAGEM_PER_PILAR = 2


@dataclass
class VM50BracingBom:
    """Contagens de VM50 e barras de ancoragem por categoria de uso."""
    lateral_viga: int = 0
    pilar_vm50: int = 0
    pilar_barras_ancoragem: int = 0
    fundo_viga: int = 0

    @property
    def total_vm50(self) -> int:
        """Total de barras VM50 a pedir (lateral + pilar + fundo)."""
        return self.lateral_viga + self.pilar_vm50 + self.fundo_viga


def _is_tower_supported(beam_result: BeamShoringResult) -> bool:
    sid = getattr(beam_result.selected_shore, "id", "") or ""
    return sid.startswith("TWR-")


def compute_vm50_bracing_bom(
    beam_results: Iterable[BeamShoringResult],
    pillar_count: int,
) -> VM50BracingBom:
    """Calcula o BOM de VM50 para travamento (lateral, pilar, fundo).

    Args:
        beam_results: resultados de escoramento por viga (usa length_m e
            shore_count; exclui vigas com selected_shore em TWR-).
        pillar_count: número de pilares detectados na planta (para a
            regra do travamento de pilar — 2 VM50 + 2 barras por pilar).
    """
    bom = VM50BracingBom()

    beams: List[BeamShoringResult] = list(beam_results)

    # 1. Travamento lateral de vigas — ceil(length / 0.90) por viga.
    for br in beams:
        length = getattr(getattr(br, "beam", None), "length_m", 0.0) or 0.0
        if length <= 0:
            continue
        bom.lateral_viga += ceil(length / VM50_LATERAL_SPACING_M)

    # 2. Travamento de pilares — 2× VM50 + 2 barras de ancoragem por pilar.
    pc = max(0, int(pillar_count))
    bom.pilar_vm50 = pc * VM50_PER_PILAR
    bom.pilar_barras_ancoragem = pc * BARRAS_ANCORAGEM_PER_PILAR

    # 3. Fundo de viga — 1 conjunto por escora com cruzeta (exclui torres).
    for br in beams:
        if _is_tower_supported(br):
            continue
        bom.fundo_viga += max(0, int(getattr(br, "shore_count", 0) or 0))

    return bom
