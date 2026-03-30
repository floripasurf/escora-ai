"""Strip shoring layers from engineer PE files, keeping only structural geometry.

Creates clean DXF files that can be fed into the Escora.AI pipeline to evaluate
how well our script reproduces the engineer's shoring decisions.

Usage:
    python3 scripts/strip_shoring.py
    python3 scripts/strip_shoring.py --input input/Sergio1 --output input/Sergio1_stripped
"""

import sys
import argparse
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

import ezdxf

# Shoring-related layer patterns — these are the engineer's shoring output
# that we want to remove so our pipeline can recalculate from scratch.
SHORING_LAYER_KEYWORDS = [
    # Tower shoring
    "TORRE_VIGA", "TORRE_LAJE", "TORRES", "Torre", "TOR_MANUAL",
    # Distribution beams
    "VM130", "VM80", "VM50", "SF250", "SF500",
    # Telescopic shores
    "TA_Viga", "TA_Laje",
    "ESC310", "ESC450", "ESC360",
    # Accessories
    "ALU14", "ALU",
    "Tirante", "Tirante_Viga",
    "Barra_Viga", "BARRA ANC", "Barra Anc",
    "Trav-Pilar",
    "Madeira",
    "Porca", "Haste LN",
    "Perfil I8",
    "MECANER",
    # Shoring misc
    "ESCLAJES",
    "PAINEL CORTE", "PAINEL 40X120",
    "CANTO EXTERNO",
    "BARRA L",
    "8X8", "8X8_LAY_OUT",
    # BOM / list of materials
    "LISTAMAT",
    # Cross-section details of shoring
    "CORTE",
    # QuikDeck formwork
    "QuikDeck",
]

# Layers to ALWAYS keep (structural, annotation, formatting)
STRUCTURAL_KEEP_LAYERS = {
    "FORMA", "VIGAS", "PILARES",
    "PILAR_RET", "PILAR_REF", "PILAR_DIM",
    "VIG_REF_VIGAS", "VIG_DIM_VIGAS", "VIG_FACES",
    "FORMATO",
    "Cotas", "COTA", "COTAS_REF_LINHAS", "COTA_FORMAS", "FCOTAS",
    "TEXTOS", "08-TEXTO", "TEXTO-CORTE", "TEXTO 03",
    "LAGENDA",
    "HACHURA", "HACHU01",
    "PENA_01", "PENA-02", "PENA_02", "PENA_04", "PENA_06",
    "CHEIA02", "TRACEJADA02", "SOMBRA",
    "NIVEL-CORTE",
    "DES_8", "DES_01", "DES_06", "DES_SIMBOLOGIA",
    "LJ_DESNIVEL", "LJ_SIMB_ABER",
    "MUR_CARAS_HORMIGON",
    "PA_NUM_ALTUR",
    "SAP_CONTORNO", "SANC_TEXTO",
    "PONTO_FIXO",
    "EIXO",
    "Defpoints",
    "S-ANNO-DIMS", "DIM01",
    "ESCRITA",
    "UTILID",
    "SUPPLIER-DESENHO", "SUPPLIER-CLIENTE", "SUPPLIER-CORTE", "SUPPLIER-TORRE_CINZA",
    "A-FLOR",
    "INSERT",
    "nome",
    "Detalhes",
    "defecto",
}

# Numeric-only layers (0, 1, 2, 3, ...) — keep them, they're usually structural/formatting
def _is_numeric_layer(name: str) -> bool:
    return name.strip().isdigit()


def is_shoring_layer(layer_name: str) -> bool:
    """Check if a layer name belongs to shoring content."""
    for keyword in SHORING_LAYER_KEYWORDS:
        if keyword.lower() in layer_name.lower():
            return True
    return False


def strip_shoring(input_path: str, output_path: str) -> dict:
    """Remove shoring entities from a DXF file.

    Returns stats about what was removed.
    """
    doc = ezdxf.readfile(input_path)
    msp = doc.modelspace()

    total = 0
    removed = 0
    kept = 0
    removed_layers = Counter()
    kept_layers = Counter()
    unknown_layers = Counter()

    entities_to_delete = []

    for entity in msp:
        total += 1
        layer = entity.dxf.layer

        if layer in STRUCTURAL_KEEP_LAYERS or _is_numeric_layer(layer):
            kept += 1
            kept_layers[layer] += 1
        elif is_shoring_layer(layer):
            removed += 1
            removed_layers[layer] += 1
            entities_to_delete.append(entity)
        elif layer == "0":
            # Layer 0 is ambiguous — keep it
            kept += 1
            kept_layers[layer] += 1
        else:
            # Unknown layer — keep it but log
            kept += 1
            unknown_layers[layer] += 1
            kept_layers[layer] += 1

    # Delete shoring entities
    for entity in entities_to_delete:
        msp.delete_entity(entity)

    # Save stripped file
    doc.saveas(output_path)

    return {
        "total": total,
        "removed": removed,
        "kept": kept,
        "removed_layers": dict(removed_layers.most_common()),
        "kept_layers": dict(kept_layers.most_common()),
        "unknown_layers": dict(unknown_layers.most_common()),
    }


def main():
    parser = argparse.ArgumentParser(description="Strip shoring layers from DXF files")
    parser.add_argument(
        "--input", type=str, default="input/Sergio1",
        help="Input directory with PE DXF files",
    )
    parser.add_argument(
        "--output", type=str, default="input/Sergio1_stripped",
        help="Output directory for stripped DXF files",
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_dir.exists():
        print(f"ERROR: Input directory not found: {input_dir}")
        return

    dxf_files = sorted(input_dir.glob("*.dxf"))
    if not dxf_files:
        print(f"No DXF files found in {input_dir}")
        return

    print("=" * 70)
    print("  ESCORA.AI — Strip Shoring from Engineer PE Files")
    print("=" * 70)

    for dxf_path in dxf_files:
        out_path = output_dir / dxf_path.name
        print(f"\n{'─' * 70}")
        print(f"  FILE: {dxf_path.name}")
        print(f"{'─' * 70}")

        try:
            stats = strip_shoring(str(dxf_path), str(out_path))

            print(f"  Total entities:   {stats['total']}")
            print(f"  Removed (shoring): {stats['removed']}")
            print(f"  Kept (structural): {stats['kept']}")
            print(f"  Removal ratio:     {stats['removed']/stats['total']:.1%}")

            print(f"\n  Removed layers:")
            for layer, count in stats["removed_layers"].items():
                print(f"    {layer:40s} {count:5d}")

            if stats["unknown_layers"]:
                print(f"\n  Unknown layers (kept):")
                for layer, count in stats["unknown_layers"].items():
                    print(f"    {layer:40s} {count:5d}")

            print(f"\n  Saved: {out_path}")

        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\n{'=' * 70}")
    print(f"  Stripped files saved to: {output_dir}/")
    print(f"  Run pipeline: python3 scripts/run_pipeline.py input/Sergio1_stripped/")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
