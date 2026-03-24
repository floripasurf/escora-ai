"""Geração de arquivo DXF com escoras posicionadas."""

import ezdxf
from ezdxf.enums import TextEntityAlignment
from typing import List
from src.models.project import ShoringResult


def generate_output_dxf(results: List[ShoringResult], output_path: str) -> str:
    """
    Gera DXF de saída com geometria original + escoras posicionadas.

    Layers criados:
    - ESTRUTURA: geometria original da laje
    - ESCORAS: círculos representando escoras
    - TEXTO_ESCORAS: código do modelo ao lado de cada escora
    - INFO: informações gerais (título, cargas)
    """
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Criar layers
    doc.layers.add("ESTRUTURA", color=7)       # Branco
    doc.layers.add("ESCORAS", color=1)         # Vermelho
    doc.layers.add("TEXTO_ESCORAS", color=3)   # Verde
    doc.layers.add("INFO", color=5)            # Azul

    for result in results:
        slab = result.slab

        # Desenhar contorno da laje
        if hasattr(slab.polygon, "exterior"):
            coords = list(slab.polygon.exterior.coords)
            msp.add_lwpolyline(
                [(x, y) for x, y in coords],
                close=True,
                dxfattribs={"layer": "ESTRUTURA"},
            )

        # Desenhar escoras
        shore_radius = 0.05  # 5cm de raio visual
        for shore in result.shores:
            # Círculo representando a escora
            msp.add_circle(
                center=(shore.x, shore.y),
                radius=shore_radius,
                dxfattribs={"layer": "ESCORAS"},
            )

            # Texto com modelo da escora
            msp.add_text(
                shore.shore.id,
                height=0.08,
                dxfattribs={
                    "layer": "TEXTO_ESCORAS",
                    "insert": (shore.x + 0.1, shore.y + 0.1),
                },
            )

        # Info da laje
        bb = slab.bounding_box
        info_y = bb.max_y + 0.5
        msp.add_text(
            f"Laje: {slab.layer_name} | "
            f"Area: {slab.area_m2:.2f}m² | "
            f"Esp: {slab.thickness_m*100:.0f}cm | "
            f"Carga: {result.total_load_kn:.1f}kN",
            height=0.12,
            dxfattribs={
                "layer": "INFO",
                "insert": (bb.min_x, info_y),
            },
        )
        msp.add_text(
            f"Escoras: {len(result.shores)}x {result.selected_shore.model} | "
            f"Grid: {result.grid_nx}x{result.grid_ny} | "
            f"Esp: {result.spacing_x_m:.2f}x{result.spacing_y_m:.2f}m",
            height=0.10,
            dxfattribs={
                "layer": "INFO",
                "insert": (bb.min_x, info_y + 0.25),
            },
        )

    doc.saveas(output_path)
    return output_path
