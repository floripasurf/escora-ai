#!/usr/bin/env python3
"""Generate output DXF from the full pipeline (multi-slab/beam).

Usage:
    python3 scripts/generate_output_dxf.py <input.dxf> [-o output.dxf] [--clean]

If -o is omitted, output goes to output/<project_id>_escoras.dxf
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="Run full pipeline and generate output DXF")
    parser.add_argument("input_dxf", help="Path to structural DXF")
    parser.add_argument("-o", "--output", help="Output DXF path (default: output/<name>_escoras.dxf)")
    parser.add_argument("--clean", action="store_true", help="Clean mode (new DXF) instead of overlay")
    args = parser.parse_args()

    input_path = Path(args.input_dxf)
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        out_dir = ROOT / "output"
        out_dir.mkdir(exist_ok=True)
        output_path = str(out_dir / f"{input_path.stem}_escoras.dxf")

    print(f"Running pipeline on: {input_path.name}")
    from src.pipeline.runner import run_pipeline
    result = run_pipeline(str(input_path))

    if result.calculation is None:
        print(f"Error: pipeline produced no calculation result")
        for w in result.warnings:
            print(f"  WARNING: {w}")
        sys.exit(1)

    calc = result.calculation
    print(f"  Slabs: {len(calc.slab_results)}, Beams: {len(calc.beam_results)}, "
          f"Total shores: {calc.total_shores}")

    # Generate output DXF
    from src.output.dxf_generator import generate_dxf
    mode = "clean" if args.clean else "overlay"
    saved = generate_dxf(str(input_path), calc, output_path, mode=mode)
    print(f"Output DXF: {saved}")

    # Print violations summary if any
    if result.violations:
        print(f"\n  Rule violations: {len(result.violations)}")
        for v in result.violations[:10]:
            print(f"    [{v.severity}] {v.rule_id}: {v.message}")
        if len(result.violations) > 10:
            print(f"    ... and {len(result.violations) - 10} more")


if __name__ == "__main__":
    main()
