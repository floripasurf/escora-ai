"""
Gera arquivos DXF de teste para o Escora.AI.

Uso: python scripts/create_test_dxf.py
"""

import ezdxf
from pathlib import Path


def create_simple_slab(output_dir: Path) -> str:
    """Cria DXF com uma laje retangular 4x6m, espessura 12cm."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    doc.layers.add("LAJE_12CM", color=1)

    # Laje retangular 4m x 6m
    msp.add_lwpolyline(
        [(0, 0), (6, 0), (6, 4), (0, 4)],
        close=True,
        dxfattribs={"layer": "LAJE_12CM"},
    )

    path = str(output_dir / "simple_slab.dxf")
    doc.saveas(path)
    print(f"  Criado: {path}")
    return path


def create_two_slabs(output_dir: Path) -> str:
    """Cria DXF com duas lajes separadas por uma viga."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    doc.layers.add("LAJE_12CM", color=1)
    doc.layers.add("LAJE_15CM", color=2)
    doc.layers.add("VIGA", color=3)

    # Laje 1: 4x5m, 12cm
    msp.add_lwpolyline(
        [(0, 0), (5, 0), (5, 4), (0, 4)],
        close=True,
        dxfattribs={"layer": "LAJE_12CM"},
    )

    # Laje 2: 4x5m, 15cm
    msp.add_lwpolyline(
        [(5.3, 0), (10.3, 0), (10.3, 4), (5.3, 4)],
        close=True,
        dxfattribs={"layer": "LAJE_15CM"},
    )

    # Viga entre as lajes (representada como retângulo estreito)
    msp.add_lwpolyline(
        [(5, 0), (5.3, 0), (5.3, 4), (5, 4)],
        close=True,
        dxfattribs={"layer": "VIGA"},
    )

    path = str(output_dir / "two_slabs.dxf")
    doc.saveas(path)
    print(f"  Criado: {path}")
    return path


def create_thick_slab(output_dir: Path) -> str:
    """Cria DXF com uma laje espessa 8x10m, espessura 25cm."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    doc.layers.add("LAJE_25CM", color=4)

    msp.add_lwpolyline(
        [(0, 0), (10, 0), (10, 8), (0, 8)],
        close=True,
        dxfattribs={"layer": "LAJE_25CM"},
    )

    path = str(output_dir / "thick_slab.dxf")
    doc.saveas(path)
    print(f"  Criado: {path}")
    return path


def main():
    output_dir = Path(__file__).parent.parent / "data" / "test_files"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Gerando arquivos DXF de teste...")
    create_simple_slab(output_dir)
    create_two_slabs(output_dir)
    create_thick_slab(output_dir)
    print("Pronto!")


if __name__ == "__main__":
    main()
