"""VM50 bracing BOM — Orguel Q4.

A VM50 tem três usos práticos no canteiro que precisam entrar no BOM
como peças separadas dos trilhos de distribuição:

1. **Travamento lateral de vigas**: barras horizontais que amarram as
   formas laterais da viga, distribuídas a cada 0.80-1.0 m. Usamos
   `VM50_LATERAL_SPACING_M = 0.90 m` (midpoint da faixa informada).

2. **Travamento de pilares**: o "conjunto" do DOCX (resposta 4) é
   2× VM (VM50 ou VM80) + 2 barras de ancoragem POR NÍVEL de travamento
   em um par de faces — NÃO por pilar. O BOM correto por pilar depende
   da seção e da altura (manual §15.1, pendência 19):

   - faces até 25 cm  → 2 lados por nível (ex. 25/75: 10 VM80 em 5 níveis);
   - faces > 40 cm    → 4 lados por nível (ex. 40x70: 20 VM50 = 5 níveis
     × 4 lados, Orguel p.63 — CORRIGIDO 2026-06-11, não 10x);
   - faces > 90 cm    → adicionar VM vertical (ex. 25x100, Orguel p.64).

   Ver `compute_pillar_bracing()` para o BOM determinístico por pilar.
   O caminho legado (`pillar_count` sem geometria) mantém 2 VM50/pilar
   por compatibilidade, mas SUBESTIMA — pendência de integração:
   `report_data.py` deve passar a geometria dos pilares.

3. **Fundo de viga**: 1 conjunto de VM50 por escora com cruzeta (viga
   escorada com telescópicas). Vigas escoradas com torres já têm o
   fundo travado via a própria torre — são excluídas aqui.

Para o BOM final, somamos as 3 categorias em `total_vm50` e reportamos
separadamente `pilar_barras_ancoragem` (peça diferente).
"""

from dataclasses import dataclass, field
from math import ceil, floor
from typing import Dict, Iterable, List

from src.models.calculation_models import BeamShoringResult


# Espaçamento de barras VM50 no travamento lateral da viga.
# Locadora informou faixa 0.80-1.0 m; usamos 0.90 m como valor de projeto.
VM50_LATERAL_SPACING_M = 0.90

# Peças por CONJUNTO de travamento de pilar (DOCX resposta 4): cada nível
# em um par de faces leva 2 VMs + 2 barras de ancoragem com porca.
# ATENÇÃO: isto é por conjunto/nível, não por pilar (manual §15.1).
VM50_PER_PILAR = 2
BARRAS_ANCORAGEM_PER_PILAR = 2

# ---------------------------------------------------------------------------
# Travamento de pilar — manual §15.1 (pendência 19)
# ---------------------------------------------------------------------------

# Limiar de face para travamento em 2 lados por nível (manual §15.1:
# "Até 25 cm → VM80 (ou VM50) + tirantes"). Acima disso usamos 4 lados
# (conservador para a faixa 25-40 cm; obrigatório para >40 cm).
PILLAR_TWO_SIDED_MAX_FACE_M = 0.25
# Face > 90 cm: adicionar VM vertical para reduzir vão entre tirantes
# (manual §15.1; exemplo canônico 25x100, Orguel p.64).
PILLAR_VERTICAL_VM_FACE_M = 0.90

# Espaçamento vertical entre conjuntos: NÃO é fixo em 80 cm. O critério
# Orguel p.64 é o vão máximo resistido pela forma, que DECRESCE com a
# pressão lateral do concreto (profundidade). Evidências:
#   - pilar 25/75:  80/80/80/80 + 20 cm na base (Orguel p.62);
#   - pilar 25x100: 34 + 7x33 + 20 cm na base, h=285 cm (Orguel p.64);
#   - JAU p.22 (compensado 18 mm): perfil 2" vai de 1.23 m (topo) a
#     0.50 m a 4 m de profundidade.
# Heurística mínima implementada (pendência 19): pilares baixos usam
# 0.80 m como default COM ALERTA (vão real depende da forma — ligar à
# tabela JAU/§23.7); pilares altos ou de face larga densificam para
# ~33 cm (o exemplo mais denso documentado, Orguel p.64).
PILLAR_SPACING_DEFAULT_M = 0.80          # Orguel p.62 (pilar 25/75)
PILLAR_SPACING_DENSE_M = 1.0 / 3.0       # Orguel p.64 (pilar 25x100, ~33 cm)
PILLAR_SPACING_BASE_OFFSET_M = 0.20      # 20 cm na base (Orguel p.62 e p.64)
# Altura até a qual o default de 0.80 m é aceito com alerta. Os exemplos
# canônicos de 80 cm (p.62-63) têm ~3.40 m; acima disso a pressão na base
# já derruba o vão do perfil 2" (JAU p.22) → densificar.
PILLAR_LOW_HEIGHT_MAX_M = 3.50

# Seleção de peças a partir dos exemplos canônicos Orguel p.62-64.
# Comprimentos de tirante disponíveis nos exemplos (mm). O catálogo JAU
# completo (650/750/1000/1300 agulha RR; 250-3000 SAE) é pendência de
# integração com o catálogo da locadora.
_TIRANTE_LENGTHS_MM = (650, 1000, 1500)
# Folga total (formas + ancoragem) usada para escolher o tirante que
# atravessa uma dimensão do pilar. Calibrada nos canônicos:
#   25 cm → 650 mm; 40 cm → 1000 mm; 70 cm → 1500 mm.
_TIRANTE_CLEARANCE_MM = 400
# Comprimentos de VM horizontais usados nos canônicos (mm).
_VM_LENGTHS_MM = (1000, 1550)


def select_tirante_mm(crossed_dimension_m: float) -> int:
    """Menor tirante canônico que atravessa a dimensão dada do pilar.

    Fonte: exemplos Orguel p.62-64 (25→650, 40→1000, 70→1500).
    """
    required = crossed_dimension_m * 1000 + _TIRANTE_CLEARANCE_MM
    for length in _TIRANTE_LENGTHS_MM:
        if length >= required:
            return length
    return _TIRANTE_LENGTHS_MM[-1]


def select_vm_length_mm(face_m: float) -> int:
    """Menor VM canônica que cobre a face do pilar.

    Fonte: exemplos Orguel p.62-64 (face 70 → VM 1000; faces 75/100 → 1550).
    Folga de 300 mm (150 por lado, passagem do tirante além do canto do
    pilar) calibrada pelos três canônicos: 700+300=1000 → VM 1000;
    750+300=1050 → VM 1550; 1000+300=1300 → VM 1550.
    """
    for length in _VM_LENGTHS_MM:
        if length >= face_m * 1000 + 300:
            return length
    return _VM_LENGTHS_MM[-1]


def pillar_bracing_spacing_m(height_m: float, max_face_m: float) -> tuple:
    """(espaçamento vertical entre conjuntos, lista de alertas).

    Heurística do manual §15.1 (ver comentário das constantes acima):
    - pilar baixo (<= 3.50 m) e face <= 90 cm → 0.80 m default + alerta;
    - pilar alto OU face > 90 cm → densifica para ~33 cm (Orguel p.64).
    """
    warnings: List[str] = []
    if height_m > PILLAR_LOW_HEIGHT_MAX_M or max_face_m > PILLAR_VERTICAL_VM_FACE_M:
        warnings.append(
            f"Espaçamento densificado para "
            f"{PILLAR_SPACING_DENSE_M*100:.0f} cm (exemplo canônico 25x100, "
            f"Orguel p.64) — confirmar com o vão admissível da forma "
            f"(§12/§23.7 e tabela JAU p.22)."
        )
        return PILLAR_SPACING_DENSE_M, warnings
    warnings.append(
        f"Espaçamento default de {PILLAR_SPACING_DEFAULT_M*100:.0f} cm "
        f"(Orguel p.62) para pilar baixo — o vão real é o máximo resistido "
        f"pela forma e decresce com a pressão (Orguel p.64 / JAU p.22); "
        f"confirmar com a forma adotada."
    )
    return PILLAR_SPACING_DEFAULT_M, warnings


@dataclass
class PillarBracingSpec:
    """BOM determinístico de travamento de um pilar (manual §15.1)."""
    levels: int = 0
    sides_per_level: int = 0
    spacing_m: float = 0.0
    vm_profile: str = "VM50"            # VM50 e VM80 são intercambiáveis
    vm_length_mm: int = 0
    vm_count: int = 0                   # VMs horizontais (níveis × lados)
    tirantes: Dict[int, int] = field(default_factory=dict)  # mm → qty
    vertical_vm_count: int = 0          # face > 90 cm (Orguel p.64)
    vertical_tirante_mm: int = 1000
    vertical_tirante_count: int = 0
    warnings: List[str] = field(default_factory=list)

    @property
    def tirante_count(self) -> int:
        return sum(self.tirantes.values()) + self.vertical_tirante_count


def compute_pillar_bracing(
    width_m: float,
    depth_m: float,
    height_m: float,
) -> PillarBracingSpec:
    """BOM de travamento de UM pilar conforme manual §15.1 (pendência 19).

    Reproduz os exemplos canônicos Orguel p.62-64:
    - 40x70, h=3.40 m → 20× VM50 1000 (5 níveis × 4 lados),
      10× tirante 1000 + 10× tirante 1500;
    - 25/75, h=3.40 m → 10× VM80 1550 (5 níveis × 2 lados),
      10× tirante 650;
    - 25x100, h=2.85 m → 16× VM80 1550 (8 níveis × 2 lados, ~33 cm),
      16× tirante 650 + 2 VM verticais + 3× tirante 1000.
    """
    spec = PillarBracingSpec()
    if width_m <= 0 or depth_m <= 0 or height_m <= 0:
        return spec

    min_face = min(width_m, depth_m)
    max_face = max(width_m, depth_m)

    spacing, warnings = pillar_bracing_spacing_m(height_m, max_face)
    spec.spacing_m = spacing
    spec.warnings.extend(warnings)

    # Níveis: 1 conjunto a cada `spacing` a partir de 20 cm da base
    # (padrão dos canônicos: 20 cm na base; último conjunto no topo ou a
    # ~1 vão dele). Epsilon evita perder nível por erro de float.
    usable = height_m - PILLAR_SPACING_BASE_OFFSET_M
    spec.levels = max(1, floor(usable / spacing + 1e-6) + 1)

    # Lados por nível (manual §15.1): menor face <= 25 cm → 2 lados;
    # senão 4 lados (canônico 40x70 = 4 lados; conservador p/ 25-40 cm).
    two_sided = min_face <= PILLAR_TWO_SIDED_MAX_FACE_M
    spec.sides_per_level = 2 if two_sided else 4

    # Perfil: até 25 cm o manual cita VM80 (ou VM50); o canônico 40x70
    # usa VM50 ("VM 50 ou VM 80" — intercambiáveis por disponibilidade).
    spec.vm_profile = "VM80" if two_sided else "VM50"
    spec.vm_length_mm = select_vm_length_mm(max_face)
    spec.vm_count = spec.levels * spec.sides_per_level

    # Tirantes: 2 por nível por direção travada. Em 2 lados, os tirantes
    # atravessam a menor dimensão; em 4 lados, 2 atravessam cada direção.
    if two_sided:
        t = select_tirante_mm(min_face)
        spec.tirantes[t] = spec.tirantes.get(t, 0) + 2 * spec.levels
    else:
        t_short = select_tirante_mm(min_face)
        t_long = select_tirante_mm(max_face)
        spec.tirantes[t_short] = spec.tirantes.get(t_short, 0) + 2 * spec.levels
        spec.tirantes[t_long] = spec.tirantes.get(t_long, 0) + 2 * spec.levels

    # Face > 90 cm: VM vertical para reduzir vão entre tirantes
    # (manual §15.1; canônico 25x100 → 2× VM80 2550 + 3× tirante 1000).
    if max_face > PILLAR_VERTICAL_VM_FACE_M:
        spec.vertical_vm_count = 2
        spec.vertical_tirante_count = 3
        spec.warnings.append(
            "Face > 90 cm: adicionadas 2 VMs verticais + 3 tirantes 1000 "
            "(manual §15.1 / exemplo canônico 25x100, Orguel p.64)."
        )

    return spec


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
