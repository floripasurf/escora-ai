#!/usr/bin/env python3
"""Phase 0 calibration runner — run pipeline against all reference DXFs.

Discovers DXFs under input/orguel_estrutural/ and input/Sergio1/,
runs the pipeline, serializes results, and generates summary CSV.

Usage:
    python3 scripts/diagnose/run_all_calibration.py
"""
import csv
import json
import logging
import sys
import traceback
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DIAGNOSTICS_DIR = ROOT / "diagnostics"
INPUT_DIRS = [
    ROOT / "input" / "orguel_estrutural",
    ROOT / "input" / "Sergio1",
]


def discover_dxfs() -> list[Path]:
    """Find all DXF files in input directories."""
    dxfs = []
    for d in INPUT_DIRS:
        if d.exists():
            dxfs.extend(sorted(d.glob("*.dxf")))
    return dxfs


def project_id(dxf_path: Path) -> str:
    """Extract project ID from filename."""
    name = dxf_path.stem
    # Use first numeric portion as ID
    parts = name.split("-")
    return parts[0].strip() if parts else name[:20]


def run_one(dxf_path: Path) -> dict:
    """Run pipeline on one DXF, return summary dict."""
    pid = project_id(dxf_path)
    out_dir = DIAGNOSTICS_DIR / pid
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "project_id": pid,
        "filename": dxf_path.name,
        "ran_ok": False,
        "total_shores": 0,
        "total_load_kn": 0.0,
        "beam_count": 0,
        "slab_count": 0,
        "warnings_count": 0,
        "violations_count": 0,
        "error": "",
    }

    try:
        from src.pipeline.runner import run_pipeline
        result = run_pipeline(str(dxf_path))

        summary["ran_ok"] = True
        summary["warnings_count"] = len(result.warnings)

        if result.calculation:
            calc = result.calculation
            summary["total_shores"] = calc.total_shores
            summary["total_load_kn"] = round(calc.total_load_kn, 2)
            summary["beam_count"] = len(calc.beam_results)
            summary["slab_count"] = len(calc.slab_results)

        summary["violations_count"] = len(result.violations)

        # Serialize result
        try:
            result_dict = result.model_dump(mode="json", exclude={"calculation": {"slab_results": {"__all__": {"polygon"}}}})
            with open(out_dir / "result.json", "w") as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Could not serialize result for {pid}: {e}")

    except Exception as e:
        summary["error"] = f"{type(e).__name__}: {e}"
        # Save error log
        with open(out_dir / "errors.log", "w") as f:
            traceback.print_exc(file=f)

    return summary


def main():
    dxfs = discover_dxfs()
    if not dxfs:
        print("No DXF files found in input directories.")
        return

    print(f"Found {len(dxfs)} DXF files. Running calibration...")
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)

    summaries = []
    for dxf in dxfs:
        pid = project_id(dxf)
        print(f"  [{len(summaries)+1}/{len(dxfs)}] {pid} ({dxf.name})...", end=" ", flush=True)
        s = run_one(dxf)
        status = "OK" if s["ran_ok"] else f"FAIL: {s['error'][:60]}"
        print(status)
        summaries.append(s)

    # Write summary CSV
    csv_path = DIAGNOSTICS_DIR / "summary.csv"
    fieldnames = [
        "project_id", "filename", "ran_ok", "total_shores", "total_load_kn",
        "beam_count", "slab_count", "warnings_count", "violations_count", "error",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)

    print(f"\nSummary written to {csv_path}")
    ok = sum(1 for s in summaries if s["ran_ok"])
    print(f"Results: {ok}/{len(summaries)} completed successfully")


if __name__ == "__main__":
    main()
