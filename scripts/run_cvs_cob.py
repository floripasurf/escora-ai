"""
Cálculo de escoramento para CVS-COB-FOR-006-R00.DXF
Dados extraídos do DXF: lajes, vigas, pilares, nível.

Uso: python scripts/run_cvs_cob.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from shapely.geometry import Polygon

from src.models.slab import Slab
from src.models.shore import PositionedShore
from src.models.project import ShoringResult
    calculate_self_weight, calculate_live_load, calculate_total_load,
)
    calculate_beam_self_weight, calculate_beam_total_linear_load,
    distribute_beam_shores, estimate_beam_shore_height,
)
from src.generator.dxf_writer import generate_output_dxf
from src.generator.bom_generator import write_bom_csv, generate_bom

console = Console()

# ============================================================
# DADOS EXTRAÍDOS DO DXF CVS-COB-FOR-006-R00
# Nível: +1330,40m (cobertura)
# Pé-direito padrão: 2.92m
# ============================================================

PE_DIREITO = 2.92  # metros

# ESCALA: Todas as coordenadas abaixo já estão em metros reais.
# Foram extraídas do DXF (escala 1:50, DXF_valor × 0.5 = metros)
# pelo script extract_alignment.py usando as POLYLINEs do Layer 11.

# ============================================================
# LAJES — Painéis retangulares extraídos das arestas de vigas (Layer 11)
#
# Cada laje é definida pelos 4 vértices do retângulo interno,
# delimitado pelas faces internas das vigas ao redor.
#
# Coordenadas em metros reais (DXF × 0.5).
# Fonte: extract_alignment.py — POLYLINEs layer 11.
# ============================================================

SLABS = [
    # L1: entre V10a(W), V8a/V11a(E), H-beam Y=17.49(S), V7a(N)
    {"name": "L1",  "thickness_cm": 18,
     "vertices": [(4.142, 17.556), (10.027, 17.556),
                  (10.027, 21.716), (4.142, 21.716)]},

    # L2: entre V11a(W), V13a(E), H-beam Y=18.33(S), V7a(N)
    {"name": "L2",  "thickness_cm": 15,
     "vertices": [(10.167, 18.396), (15.022, 18.396),
                  (15.022, 21.716), (10.167, 21.716)]},

    # L3: entre V13a(W), V15a(E), H-beam Y=18.33(S), V7a(N)
    {"name": "L3",  "thickness_cm": 10,
     "vertices": [(15.162, 18.396), (18.477, 18.396),
                  (18.477, 21.716), (15.162, 21.716)]},

    # L4: entre V12a(W), V15a/V6a(E), V7a(S), V3a(N)
    {"name": "L4",  "thickness_cm": 12,
     "vertices": [(14.052, 21.856), (18.477, 21.856),
                  (18.477, 23.041), (14.052, 23.041)]},

    # L5: forma de L — base completa (V15a→V18a) + extensão superior no gap do H-beam Y=23.116
    # O H-beam Y=23.116 tem gap entre X=19.95 e X=21.77. V16a (X=20.182) delimita o degrau.
    {"name": "L5",  "thickness_cm": 12,
     "vertices": [(18.616, 22.021), (21.632, 22.021), (21.632, 24.221),
                  (20.252, 24.221), (20.252, 23.041), (18.616, 23.041)]},

    # L6: forma de L — corpo principal (V14a→V16a) + extensão superior (V16a termina, amplia até V17a)
    {"name": "L6",  "thickness_cm": 15,
     "vertices": [(16.582, 23.191), (20.112, 23.191), (20.112, 24.361),
                  (20.872, 24.361), (20.872, 26.281), (16.582, 26.281)]},

    # L7: forma de L — base estreita (V18a→V19a) + superior ampla (V17a→V19a)
    # V18a limita à esquerda até Y=24.361, acima V17a assume o limite.
    {"name": "L7",  "thickness_cm": 10,
     "vertices": [(21.772, 23.191), (25.827, 23.191), (25.827, 26.281),
                  (21.012, 26.281), (21.012, 24.361), (21.772, 24.361)]},

    # L8: faixa entre V1a(S) e perímetro Y=27.251(N)
    {"name": "L8",  "thickness_cm": 10,
     "vertices": [(16.442, 26.421), (26.797, 26.421),
                  (26.797, 27.251), (16.442, 27.251)]},

    # L9: entre V18a(W), V19a(E), H-beam Y=18.33(S), V5a(N)
    {"name": "L9",  "thickness_cm": 10,
     "vertices": [(21.772, 18.396), (25.827, 18.396),
                  (25.827, 23.041), (21.772, 23.041)]},

    # L10: entre V15a(W), V18a(E), H-beam Y=18.33(S), V6a Y=21.88(N)
    {"name": "L10", "thickness_cm": 15,
     "vertices": [(18.616, 18.396), (21.632, 18.396),
                  (21.632, 21.881), (18.616, 21.881)]},
]

# ============================================================
# VIGAS — Trechos de fôrma entre apoios (sem duplicatas)
#
# Cada entrada é um trecho único de viga para escoramento.
# Removidos: V7a (duplicata de V9a+V10a), V11a (duplicata de V8a)
# Adicionado: V15b (2º trecho de V15a, X=18.547)
#
# Condições de contorno (NBR 6118):
#   supports: posições relativas dos apoios ao longo da viga (pilar/cruzamento)
#   cant_start/cant_end: True se extremidade livre (balanço)
# ============================================================
BEAMS = [
    # === Vigas Horizontais ===
    # V1a: P5(16.512) → V-beam(18.547) → V-beam(20.182) → P4(20.942)
    {"name": "V1a",  "w_cm": 14, "h_cm": 40, "length": 4.210,
     "start_x": 16.582, "start_y": 26.351, "direction": "x",
     "supports": [0.0, 1.965, 3.600, 4.210],  # P5, V15a, V16a, ~P4
     "cant_start": False, "cant_end": False},

    # V1b: P4(20.942) → V18a(21.702) → P6(25.897)
    {"name": "V1b",  "w_cm": 14, "h_cm": 40, "length": 4.735,
     "start_x": 21.092, "start_y": 26.351, "direction": "x",
     "supports": [0.0, 0.610, 4.735],  # ~P4, V18a, P6
     "cant_start": False, "cant_end": False},

    # V2a: BALANÇO início (0.53m) → V17a(20.942) → P9(21.622)
    {"name": "V2a",  "w_cm": 14, "h_cm": 40, "length": 1.058,
     "start_x": 20.414, "start_y": 24.291, "direction": "x",
     "supports": [0.528, 1.058],  # V17a, P9 (extremidade)
     "cant_start": True, "cant_end": False},

    # V3a: P10(13.957) → V13a(15.092) → P11(16.512)
    {"name": "V3a",  "w_cm": 19, "h_cm": 40, "length": 2.390,
     "start_x": 14.052, "start_y": 23.116, "direction": "x",
     "supports": [0.0, 1.040, 2.390],  # P10, V13a, P11
     "cant_start": False, "cant_end": False},

    # V4a: P11(16.512) → V15a(18.547)
    {"name": "V4a",  "w_cm": 14, "h_cm": 40, "length": 1.964,
     "start_x": 16.582, "start_y": 23.121, "direction": "x",
     "supports": [0.0, 1.964],  # P11, V15a
     "cant_start": False, "cant_end": False},

    # V5a: V18a(21.702) → P13(25.897)
    {"name": "V5a",  "w_cm": 14, "h_cm": 40, "length": 4.055,
     "start_x": 21.772, "start_y": 23.121, "direction": "x",
     "supports": [0.0, 4.055],  # V18a, P13
     "cant_start": False, "cant_end": False},

    # V6a: P18(18.547) → V16a(20.182) → V17a(20.942) → P17(21.702)
    {"name": "V6a",  "w_cm": 14, "h_cm": 40, "length": 3.015,
     "start_x": 18.616, "start_y": 21.951, "direction": "x",
     "supports": [0.0, 1.566, 2.326, 3.015],  # P18, V16a, V17a, P17
     "cant_start": False, "cant_end": False},

    # V7a-H: V10a(4.072) → P14(6.377) → P15(10.017) → V12a(13.982) →
    #         P16(15.172) → V14a(16.512) → P18(18.547)
    {"name": "V7a-H", "w_cm": 14, "h_cm": 60, "length": 14.478,
     "start_x": 4.002, "start_y": 21.786, "direction": "x",
     "supports": [0.070, 2.375, 6.015, 9.980, 11.170, 12.510, 14.478],
     "cant_start": False, "cant_end": False},

    # V8a-H: P19(10.097) → V12a(13.982) → P20(15.172) → V14a(16.512) →
    #         P21(18.466) → V16a(20.182) → V17a(20.942) → P22(21.782) → P23(25.817)
    {"name": "V8a-H", "w_cm": 14, "h_cm": 40, "length": 15.500,
     "start_x": 10.167, "start_y": 18.326, "direction": "x",
     "supports": [0.0, 3.815, 5.005, 6.345, 8.299, 10.015, 10.775, 11.615, 15.500],
     "cant_start": False, "cant_end": False},

    # V9a-H: V10a(4.072) → V8a(10.097)
    {"name": "V9a-H", "w_cm": 14, "h_cm": 40, "length": 5.885,
     "start_x": 4.142, "start_y": 17.486, "direction": "x",
     "supports": [0.0, 5.885],  # V10a, V8a
     "cant_start": False, "cant_end": False},

    # === Vigas Verticais ===
    # V9a: P24(16.506) → H9a-H(17.486) — sub-trecho inferior de X=4.072
    {"name": "V9a",  "w_cm": 14, "h_cm": 60, "length": 0.884,
     "start_x": 4.072, "start_y": 16.601, "direction": "y",
     "supports": [0.0, 0.884],  # P24, H-beam
     "cant_start": False, "cant_end": False},

    # V10a: H9a-H(17.486) → V7a-H(21.786) — sub-trecho superior de X=4.072
    {"name": "V10a", "w_cm": 14, "h_cm": 60, "length": 4.370,
     "start_x": 4.072, "start_y": 17.486, "direction": "y",
     "supports": [0.0, 0.840, 4.370],  # H-beam 17.49, H-beam 18.33(≈), V7a-H
     "cant_start": False, "cant_end": False},

    # V8a: P25(16.583) → H-beam(17.486) → P19(18.406) → P15(21.786)
    {"name": "V8a",  "w_cm": 14, "h_cm": 40, "length": 5.040,
     "start_x": 10.097, "start_y": 16.678, "direction": "y",
     "supports": [0.0, 0.808, 1.728, 5.040],  # P25, H-beam, P19, P15
     "cant_start": False, "cant_end": False},

    # V12a: V7a-H(21.786) → P10(23.136) — trecho curto
    {"name": "V12a", "w_cm": 14, "h_cm": 40, "length": 1.185,
     "start_x": 13.982, "start_y": 21.856, "direction": "y",
     "supports": [0.0, 1.185],  # V7a-H, P10
     "cant_start": False, "cant_end": False},

    # V13a: P20(18.326) → P16(21.786)
    {"name": "V13a", "w_cm": 14, "h_cm": 40, "length": 3.320,
     "start_x": 15.092, "start_y": 18.396, "direction": "y",
     "supports": [0.0, 3.320],  # P20, P16
     "cant_start": False, "cant_end": False},

    # V14a: BALANÇO início (0.95m até H-beam 24.291) → P5(26.271)
    {"name": "V14a", "w_cm": 14, "h_cm": 40, "length": 2.780,
     "start_x": 16.512, "start_y": 23.341, "direction": "y",
     "supports": [0.950, 2.780],  # H-beam 24.291, P5
     "cant_start": True, "cant_end": False},

    # V15a: P21(18.326) → P20×(?) — trecho 1 até cruzamento com V7a-H
    {"name": "V15a", "w_cm": 14, "h_cm": 40, "length": 3.140,
     "start_x": 18.547, "start_y": 18.396, "direction": "y",
     "supports": [0.0, 3.140],  # P21, V7a-H (extremidade superior)
     "cant_start": False, "cant_end": False},

    # V15b: 2º trecho de X=18.547, entre V6a(22.021) e H-beam(23.041)
    {"name": "V15b", "w_cm": 14, "h_cm": 40, "length": 1.010,
     "start_x": 18.547, "start_y": 22.040, "direction": "y",
     "supports": [0.0, 1.010],  # V6a, H-beam 23.116
     "cant_start": False, "cant_end": False},

    # V16a: P12(23.121) → P8(24.291)
    {"name": "V16a", "w_cm": 14, "h_cm": 40, "length": 1.030,
     "start_x": 20.182, "start_y": 23.191, "direction": "y",
     "supports": [0.0, 1.030],  # P12, P8
     "cant_start": False, "cant_end": False},

    # V17a: H-beam(24.291) → P4(26.351)
    {"name": "V17a", "w_cm": 14, "h_cm": 40, "length": 1.920,
     "start_x": 20.942, "start_y": 24.361, "direction": "y",
     "supports": [0.0, 1.920],  # H-beam 24.291, P4
     "cant_start": False, "cant_end": False},

    # V18a: P22(18.326) → V7a-H(21.786) → P17(21.951) → H-beam(23.116) → P9(24.291)
    {"name": "V18a", "w_cm": 14, "h_cm": 40, "length": 5.825,
     "start_x": 21.702, "start_y": 18.396, "direction": "y",
     "supports": [0.0, 3.390, 3.555, 4.720, 5.825],  # P22, V7a-H, P17, H23.1, P9
     "cant_start": False, "cant_end": False},

    # V19a: P23(18.326) → V7a-H(21.786) → H-beam(21.951) → P13(23.121) →
    #        H-beam(24.291) → P6(26.271)
    {"name": "V19a", "w_cm": 14, "h_cm": 40, "length": 7.725,
     "start_x": 25.897, "start_y": 18.396, "direction": "y",
     "supports": [0.0, 3.390, 3.555, 4.725, 5.895, 7.725],
     "cant_start": False, "cant_end": False},
]


# ============================================================
# PILARES — Posições precisas dos centróides de SOLIDs (layers 21/22)
# Dimensões em cm (largura × profundidade)
# ============================================================
PILLARS = [
    {"name": "P1",  "x": 6.377,  "y": 26.616, "w_cm": 30, "d_cm": 14},
    {"name": "P2",  "x": 10.017, "y": 26.616, "w_cm": 30, "d_cm": 14},
    {"name": "P3",  "x": 13.902, "y": 26.616, "w_cm": 30, "d_cm": 14},
    {"name": "P4",  "x": 20.942, "y": 26.351, "w_cm": 30, "d_cm": 14},
    {"name": "P5",  "x": 16.512, "y": 26.271, "w_cm": 14, "d_cm": 30},
    {"name": "P6",  "x": 25.897, "y": 26.271, "w_cm": 14, "d_cm": 30},
    {"name": "P7",  "x": 4.072,  "y": 25.891, "w_cm": 14, "d_cm": 30},
    {"name": "P8",  "x": 20.262, "y": 24.291, "w_cm": 30, "d_cm": 14},
    {"name": "P9",  "x": 21.622, "y": 24.291, "w_cm": 30, "d_cm": 14},
    {"name": "P10", "x": 13.957, "y": 23.136, "w_cm": 19, "d_cm": 19},
    {"name": "P11", "x": 16.512, "y": 23.191, "w_cm": 14, "d_cm": 30},
    {"name": "P12", "x": 20.102, "y": 23.121, "w_cm": 30, "d_cm": 14},
    {"name": "P13", "x": 25.897, "y": 23.121, "w_cm": 14, "d_cm": 30},
    {"name": "P14", "x": 6.377,  "y": 21.786, "w_cm": 30, "d_cm": 14},
    {"name": "P15", "x": 10.017, "y": 21.786, "w_cm": 30, "d_cm": 14},
    {"name": "P16", "x": 15.172, "y": 21.786, "w_cm": 30, "d_cm": 14},
    {"name": "P17", "x": 21.702, "y": 21.951, "w_cm": 14, "d_cm": 30},
    {"name": "P18", "x": 18.547, "y": 21.946, "w_cm": 14, "d_cm": 18},
    {"name": "P19", "x": 10.097, "y": 18.406, "w_cm": 14, "d_cm": 30},
    {"name": "P20", "x": 15.172, "y": 18.326, "w_cm": 30, "d_cm": 14},
    {"name": "P21", "x": 18.466, "y": 18.326, "w_cm": 30, "d_cm": 14},
    {"name": "P22", "x": 21.782, "y": 18.326, "w_cm": 30, "d_cm": 14},
    {"name": "P23", "x": 25.817, "y": 18.326, "w_cm": 30, "d_cm": 14},
    {"name": "P24", "x": 4.097,  "y": 16.506, "w_cm": 19, "d_cm": 19},
    {"name": "P25", "x": 10.099, "y": 16.583, "w_cm": 19, "d_cm": 19},
]

# Todos os pilares servem como zonas de exclusão globais
# O distribuidor verifica proximidade de cada posição de escora contra todos os pilares
ALL_PILLAR_EXCLUSIONS = None  # será construído no main()


def build_exclusions_for_slab(slab_polygon):
    """Constrói zonas de exclusão apenas para pilares próximos da laje.

    Verifica se a zona de exclusão do pilar intercepta o polígono da laje.
    Pilares distantes são ignorados automaticamente.
    """
    from shapely.geometry import box as shapely_box

    exclusions = []
    for p in PILLARS:
        exc = PillarExclusion(
            cx=p["x"], cy=p["y"],
            width_m=p["w_cm"] / 100.0,
            depth_m=p["d_cm"] / 100.0,
        )
        # Só incluir se a zona de exclusão intercepta a laje
        exc_box = shapely_box(exc.min_x, exc.min_y, exc.max_x, exc.max_y)
        if slab_polygon.intersects(exc_box):
            exclusions.append(exc)
    return exclusions


DIST_INFLUENCIA_VIGA = 0.40  # Área de influência da escora de viga (m)
# A viga e suas escoras já suportam a laje na faixa adjacente.
# Escoras de laje dentro desta zona são redundantes e devem ser evitadas.
# 0.40m da face da viga: garante que escoras de laje fiquem a pelo menos
# ~0.47m do eixo da viga (0.40 + meia largura), evitando proximidade
# sem ser excessivo para lajes estreitas.


def build_beam_axis_exclusions(beams_data):
    """Cria zonas de exclusão ao longo do eixo de cada viga (faixa contínua).

    Cada viga gera uma faixa retangular de exclusão ao longo de todo o seu
    comprimento, com margem DIST_INFLUENCIA_VIGA de cada lado da face da viga.
    Isso impede que escoras de laje sejam posicionadas na área de influência
    das escoras de viga, onde o suporte já é garantido pela viga e suas escoras.
    """
    exclusions = []
    for b in beams_data:
        w_m = b["w_cm"] / 100.0
        sx = b.get("start_x", 0)
        sy = b.get("start_y", 0)
        length = b["length"]
        direction = b.get("direction", "x")

        if direction == "x":
            # Viga horizontal: faixa ao longo de X
            cx = sx + length / 2
            cy = sy
            exc = PillarExclusion(
                cx=cx, cy=cy,
                width_m=length,   # comprimento da viga em X
                depth_m=w_m,      # largura da viga em Y
                margin=DIST_INFLUENCIA_VIGA,
            )
        else:
            # Viga vertical: faixa ao longo de Y
            cx = sx
            cy = sy + length / 2
            exc = PillarExclusion(
                cx=cx, cy=cy,
                width_m=w_m,      # largura da viga em X
                depth_m=length,   # comprimento da viga em Y
                margin=DIST_INFLUENCIA_VIGA,
            )
        exclusions.append(exc)
    return exclusions


def generate_combined_dxf(slab_results, beam_shores, beams_data, output_path):
    """Gera DXF completo com vigas, pilares, escoras de viga e escoras de laje."""
    import ezdxf

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Layers
    doc.layers.add("PILARES", color=1)           # Vermelho
    doc.layers.add("VIGAS", color=5)              # Azul
    doc.layers.add("LAJES", color=7)              # Branco
    doc.layers.add("ESCORAS_VIGAS", color=6)      # Magenta
    doc.layers.add("ESCORAS_LAJES", color=3)      # Verde
    doc.layers.add("TEXTO", color=8)              # Cinza
    doc.layers.add("INFO", color=4)               # Cyan

    # Desenhar pilares
    for p in PILLARS:
        w = p["w_cm"] / 100.0
        d = p["d_cm"] / 100.0
        x1 = p["x"] - w / 2
        y1 = p["y"] - d / 2
        x2 = p["x"] + w / 2
        y2 = p["y"] + d / 2
        msp.add_lwpolyline(
            [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
            close=True,
            dxfattribs={"layer": "PILARES"},
        )
        msp.add_text(
            p["name"], height=0.10,
            dxfattribs={"layer": "TEXTO", "insert": (p["x"] - 0.12, p["y"] + d / 2 + 0.05)},
        )

    # Desenhar vigas (retângulos das arestas)
    for b in beams_data:
        w_m = b["w_cm"] / 100.0
        hw = w_m / 2
        sx = b.get("start_x", 0)
        sy = b.get("start_y", 0)
        length = b["length"]
        direction = b.get("direction", "x")

        if direction == "x":
            msp.add_lwpolyline(
                [(sx, sy - hw), (sx + length, sy - hw),
                 (sx + length, sy + hw), (sx, sy + hw)],
                close=True,
                dxfattribs={"layer": "VIGAS"},
            )
        else:
            msp.add_lwpolyline(
                [(sx - hw, sy), (sx + hw, sy),
                 (sx + hw, sy + length), (sx - hw, sy + length)],
                close=True,
                dxfattribs={"layer": "VIGAS"},
            )

    # Desenhar contornos das lajes e escoras de laje
    for result in slab_results:
        slab = result.slab
        if hasattr(slab.polygon, "exterior"):
            coords = list(slab.polygon.exterior.coords)
            msp.add_lwpolyline(
                [(x, y) for x, y in coords],
                close=True,
                dxfattribs={"layer": "LAJES"},
            )

        # Escoras de laje — quadrado 10×10cm
        for shore in result.shores:
            s = 0.05
            msp.add_lwpolyline(
                [(shore.x - s, shore.y - s), (shore.x + s, shore.y - s),
                 (shore.x + s, shore.y + s), (shore.x - s, shore.y + s)],
                close=True,
                dxfattribs={"layer": "ESCORAS_LAJES"},
            )

        # Info da laje
        bb = slab.bounding_box
        cx = (bb.min_x + bb.max_x) / 2
        cy = (bb.min_y + bb.max_y) / 2
        msp.add_text(
            f"{slab.layer_name.split('_')[0]} ({len(result.shores)}esc)",
            height=0.10,
            dxfattribs={"layer": "INFO", "insert": (cx - 0.4, cy)},
        )

    # Escoras de viga — círculo Ø10cm
    for bs in beam_shores:
        msp.add_circle(
            center=(bs.x, bs.y),
            radius=0.05,
            dxfattribs={"layer": "ESCORAS_VIGAS"},
        )

    doc.saveas(output_path)


def main():
    catalog = load_catalog()

    console.print()
    console.print(Panel.fit(
        "[bold]ESCORA.AI — CVS-COB-FOR-006-R00[/bold]\n"
        "Fôrma da Cobertura — Nível +1330,40m",
        border_style="red",
    ))
    console.print()

    # ============================================================
    # FASE 1: VIGAS (calculadas primeiro — definem zonas de exclusão)
    # ============================================================
    console.print(Panel("[bold]FASE 1 — VIGAS[/bold]", border_style="red"))

    beam_table = Table(title="Escoramento de Vigas")
    beam_table.add_column("Viga", style="cyan")
    beam_table.add_column("Seção", style="white")
    beam_table.add_column("Compr.", style="white")
    beam_table.add_column("Tipo", style="magenta")
    beam_table.add_column("Carga (kN/m)", style="yellow")
    beam_table.add_column("Escoras", style="green")
    beam_table.add_column("Espaç.", style="white")
    beam_table.add_column("Modelo", style="white")
    beam_table.add_column("Utiliz.", style="white")

    all_beam_shores = []
    total_beam_shores = 0

    for b in BEAMS:
        w_m = b["w_cm"] / 100.0
        h_m = b["h_cm"] / 100.0
        length = b["length"]

        shore_height = estimate_beam_shore_height(PE_DIREITO, h_m)
        q_linear = calculate_beam_total_linear_load(w_m, h_m)

        max_spacing_beam = 0.80 if b["h_cm"] >= 60 else 1.00

        estimated_load = q_linear * max_spacing_beam
        shore = select_shore(catalog, shore_height, estimated_load)
        if shore is None:
            shore = select_shore(catalog, shore_height, 5.0)

        shores, n, spacing = distribute_beam_shores(
            length, w_m, h_m, shore, q_linear,
            max_spacing=max_spacing_beam,
            start_x=b.get("start_x", 0.0),
            start_y=b.get("start_y", 0.0),
            direction=b.get("direction", "x"),
            support_positions=b.get("supports"),
            is_cantilever_start=b.get("cant_start", False),
            is_cantilever_end=b.get("cant_end", False),
        )
        total_beam_shores += len(shores)
        all_beam_shores.extend(shores)

        load_per = q_linear * spacing if spacing > 0 else 0
        utilization = load_per / shore.load_capacity_kn if spacing > 0 else 0

        # Tipo de apoio (NBR 6118)
        if b.get("cant_start") or b.get("cant_end"):
            tipo = "Balanço"
        else:
            tipo = "Apoiada"

        beam_table.add_row(
            b["name"],
            f"{b['w_cm']}/{b['h_cm']}",
            f"{length:.1f}m",
            tipo,
            f"{q_linear:.2f}",
            str(len(shores)),
            f"{spacing:.2f}m",
            shore.model.split(" ")[1],
            f"{'[green]' if utilization <= 0.8 else '[yellow]'}{utilization:.0%}",
        )

    console.print(beam_table)
    console.print(f"\n  [bold]{total_beam_shores}[/bold] escoras de viga posicionadas → "
                  f"faixa de influência ({DIST_INFLUENCIA_VIGA:.2f}m) exclui lajes próximas\n")

    # ============================================================
    # FASE 2: LAJES (respeitando escoras de viga + pilares)
    # ============================================================
    console.print(Panel("[bold]FASE 2 — LAJES (respeitando vigas)[/bold]", border_style="cyan"))

    # Construir exclusões por faixa de influência das vigas (eixo completo)
    beam_exclusions = build_beam_axis_exclusions(BEAMS)
    console.print(f"  Zonas de exclusão: {len(PILLARS)} pilares + "
                  f"{len(beam_exclusions)} vigas (faixa {DIST_INFLUENCIA_VIGA:.2f}m)\n")

    slab_table = Table(title="Escoramento de Lajes")
    slab_table.add_column("Laje", style="cyan")
    slab_table.add_column("Esp.", style="white")
    slab_table.add_column("Área (m²)", style="white")
    slab_table.add_column("Carga (kN)", style="yellow")
    slab_table.add_column("Escoras", style="green")
    slab_table.add_column("Grid", style="white")
    slab_table.add_column("Espaç. (m)", style="white")
    slab_table.add_column("Modelo", style="white")
    slab_table.add_column("Utiliz.", style="white")

    all_slab_results = []
    total_slab_shores = 0
    excluded_by_pillars = 0
    excluded_by_beams = 0

    for s in SLABS:
        thickness_m = s["thickness_cm"] / 100.0
        polygon = Polygon(s["vertices"])
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        slab = Slab.from_polygon(polygon, f"{s['name']}_h{s['thickness_cm']}", thickness_m)

        # Montar exclusões: pilares + escoras de viga próximas
        pillar_excl = build_exclusions_for_slab(polygon)
        # Filtrar exclusões de viga que interceptam este painel
        from shapely.geometry import box as shapely_box
        beam_excl_for_slab = []
        for exc in beam_exclusions:
            exc_box = shapely_box(exc.min_x, exc.min_y, exc.max_x, exc.max_y)
            if polygon.intersects(exc_box):
                beam_excl_for_slab.append(exc)

        all_exclusions = pillar_excl + beam_excl_for_slab

        shore_height = PE_DIREITO - thickness_m
        total_load = calculate_total_load(slab)

        estimated = total_load / max(1, int(slab.area_m2 / 2.25))
        shore = select_shore(catalog, shore_height, estimated)
        if shore is None:
            shore = select_shore(catalog, shore_height, 5.0)
        if shore is None:
            candidates = [c for c in catalog if c.height_min_m <= shore_height <= c.height_max_m]
            if candidates:
                shore = max(candidates, key=lambda c: c.load_capacity_kn)
            else:
                shore = catalog[0]

        # Grid mais denso (1.0m) para compensar exclusões de vigas e
        # garantir posições válidas no interior da laje.
        shores, nx, ny, sx, sy = distribute_shores(
            slab, shore, total_load, max_spacing=1.0, exclusions=all_exclusions,
        )
        if not shores:
            console.print(f"[yellow]Aviso: {s['name']} sem escoras[/yellow]")
            continue

        load_per_shore = total_load / len(shores)

        if load_per_shore > shore.load_capacity_kn:
            stronger = select_shore(catalog, shore_height, load_per_shore)
            if stronger is not None:
                shore = stronger
                shores, nx, ny, sx, sy = distribute_shores(
                    slab, shore, total_load, max_spacing=1.0, exclusions=all_exclusions,
                )
                load_per_shore = total_load / len(shores) if shores else 0

        utilization = load_per_shore / shore.load_capacity_kn
        total_slab_shores += len(shores)

        grid_total = nx * ny
        removed = grid_total - len(shores)
        excluded_by_pillars += len(pillar_excl)
        excluded_by_beams += len(beam_excl_for_slab)

        slab_table.add_row(
            s["name"],
            f"{s['thickness_cm']}cm",
            f"{slab.area_m2:.1f}",
            f"{total_load:.1f}",
            str(len(shores)),
            f"{nx}×{ny}",
            f"{sx:.2f}×{sy:.2f}",
            shore.model.split(" ")[1],
            f"{'[green]' if utilization <= 0.8 else '[yellow]'}{utilization:.0%}",
        )

        all_slab_results.append(ShoringResult(
            slab=slab,
            total_load_kn=round(total_load, 2),
            self_weight_kn=round(calculate_self_weight(slab), 2),
            live_load_kn=round(calculate_live_load(slab), 2),
            selected_shore=shore,
            shores=shores,
            grid_nx=nx, grid_ny=ny,
            spacing_x_m=round(sx, 4), spacing_y_m=round(sy, 4),
            load_per_shore_kn=round(load_per_shore, 2),
        ))

    console.print(slab_table)
    console.print()

    # ============================================================
    # RESUMO GERAL
    # ============================================================
    total = total_slab_shores + total_beam_shores
    total_weight_slabs = sum(
        len(r.shores) * r.selected_shore.weight_kg for r in all_slab_results
    )
    total_weight_beams = sum(s.shore.weight_kg for s in all_beam_shores)

    summary = Table(title="Resumo Geral", show_header=False)
    summary.add_column("", style="cyan")
    summary.add_column("", style="white")
    summary.add_row("Pé-direito", f"{PE_DIREITO:.2f} m")
    summary.add_row("Nível", "+1330,40 m")
    summary.add_row("", "")
    summary.add_row("Escoras em vigas", f"{total_beam_shores}")
    summary.add_row("Escoras em lajes", f"{total_slab_shores}")
    summary.add_row("[bold]Total de escoras", f"[bold]{total}")
    summary.add_row("", "")
    summary.add_row("Pilares no projeto", f"{len(PILLARS)}")
    summary.add_row("Excl. por pilares (zonas)", f"{excluded_by_pillars}")
    summary.add_row("Excl. por vigas (zonas)", f"{excluded_by_beams}")
    summary.add_row("Área influência viga", f"{DIST_INFLUENCIA_VIGA:.2f} m")
    summary.add_row("", "")
    summary.add_row("Peso total (vigas)", f"{total_weight_beams:.0f} kg")
    summary.add_row("Peso total (lajes)", f"{total_weight_slabs:.0f} kg")
    summary.add_row("[bold]Peso total", f"[bold]{total_weight_slabs + total_weight_beams:.0f} kg")
    console.print(summary)
    console.print()

    # Gerar outputs
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # DXF completo: vigas + lajes + escoras
    dxf_path = str(output_dir / "CVS-COB-escoras.dxf")
    generate_combined_dxf(all_slab_results, all_beam_shores, BEAMS, dxf_path)
    console.print(f"[green]DXF completo:[/green] {dxf_path}")

    write_bom_csv(all_slab_results, str(output_dir / "CVS-COB-bom-completo.csv"))
    console.print(f"[green]BOM:[/green] output/CVS-COB-bom-completo.csv")
    console.print()


if __name__ == "__main__":
    main()
