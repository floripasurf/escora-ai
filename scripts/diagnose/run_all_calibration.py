#!/usr/bin/env python3
"""Run the current Escora pipeline against the Supplier calibration set.

This is a Phase 0 diagnostic tool. It must not modify pipeline behavior.
When CAD/runtime dependencies are unavailable, it still writes a complete
inventory row per project so the missing setup is visible instead of silent.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import os
import re
import sys
import traceback
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUMMARY_FIELDS = [
    "project_id",
    "shoring_dxf",
    "structural_dxf",
    "ran_to_completion",
    "bom_kg_total",
    "kg_per_m3",
    "tower_count",
    "telescopic_count",
    "exceptions_count",
    "error_type",
    "error_message",
    "output_dir",
]


@dataclass(frozen=True)
class CalibrationProject:
    project_id: str
    shoring_dxf: Path
    structural_dxf: Path | None


def slugify_stem(stem: str) -> str:
    """Return a stable ASCII-ish project id from a DXF stem."""
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.replace("_escoras", "")
    ascii_text = ascii_text.replace("_estrutural", "")
    ascii_text = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text)
    return ascii_text.strip("-").upper()


def _structural_key(path: Path) -> str:
    return slugify_stem(path.stem)


def discover_calibration_projects(root: Path) -> list[CalibrationProject]:
    """Discover the 12 Supplier shoring DXFs and matching structural DXFs."""
    supplier_dir = root / "input" / "supplier"
    structural_dir = root / "input" / "supplier_estrutural"

    shoring_files = sorted(supplier_dir.glob("*.dxf"))
    structural_by_key = {
        _structural_key(path): path for path in sorted(structural_dir.glob("*.dxf"))
    }

    projects: list[CalibrationProject] = []
    for shoring_path in shoring_files:
        project_id = slugify_stem(shoring_path.stem)
        structural_path = structural_by_key.get(project_id)
        projects.append(
            CalibrationProject(
                project_id=project_id,
                shoring_dxf=shoring_path,
                structural_dxf=structural_path,
            )
        )
    return projects


def _dependency_error() -> str | None:
    required = ["ezdxf", "shapely", "pydantic", "fastapi"]
    missing = []
    for module_name in required:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)
    if missing:
        return "missing dependencies: " + ", ".join(missing)
    return None


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _summarize_result(result: dict[str, Any]) -> tuple[float, float]:
    total_kg = 0.0
    total_volume = 0.0
    for row in result.get("consumption_summary") or []:
        total_kg += _safe_float(row.get("total_kg"))
        total_volume += _safe_float(row.get("volume_bruto_m3"))
    kg_per_m3 = total_kg / total_volume if total_volume > 0 else 0.0
    return total_kg, kg_per_m3


def run_project(root: Path, out_dir: Path, project: CalibrationProject) -> dict[str, Any]:
    project_dir = out_dir / project.project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    row: dict[str, Any] = {
        "project_id": project.project_id,
        "shoring_dxf": str(project.shoring_dxf),
        "structural_dxf": str(project.structural_dxf or ""),
        "ran_to_completion": "false",
        "bom_kg_total": "",
        "kg_per_m3": "",
        "tower_count": "",
        "telescopic_count": "",
        "exceptions_count": "0",
        "error_type": "",
        "error_message": "",
        "output_dir": str(project_dir),
    }

    dependency_error = _dependency_error()
    if dependency_error:
        row["exceptions_count"] = "1"
        row["error_type"] = "DependencyUnavailable"
        row["error_message"] = dependency_error
        (project_dir / "errors.log").write_text(dependency_error + "\n", encoding="utf-8")
        return row

    original_data_dir = os.environ.get("ESCORA_DATA_DIR")
    os.environ["ESCORA_DATA_DIR"] = str(out_dir)
    sys.path.insert(0, str(root))
    try:
        from api.services.pipeline_service import process_dxf

        result = process_dxf(
            input_path=str(project.structural_dxf or project.shoring_dxf),
            job_id=project.project_id,
            mode="inventory",
            inventory_name="supplier_sjc",
            branch_id="diagnostics-supplier",
        )
        if result.get("error"):
            raise RuntimeError(str(result["error"]))

        total_kg, kg_per_m3 = _summarize_result(result)
        row["ran_to_completion"] = "true"
        row["bom_kg_total"] = f"{total_kg:.2f}"
        row["kg_per_m3"] = f"{kg_per_m3:.2f}"
        row["tower_count"] = ""
        row["telescopic_count"] = str(result.get("total_shores", ""))
        row["output_dir"] = str(out_dir / "output" / project.project_id)
        return row
    except Exception as exc:
        row["exceptions_count"] = "1"
        row["error_type"] = type(exc).__name__
        row["error_message"] = str(exc)
        (project_dir / "errors.log").write_text(
            "".join(traceback.format_exception(exc)),
            encoding="utf-8",
        )
        return row
    finally:
        if str(root) in sys.path:
            sys.path.remove(str(root))
        if original_data_dir is None:
            os.environ.pop("ESCORA_DATA_DIR", None)
        else:
            os.environ["ESCORA_DATA_DIR"] = original_data_dir


def write_summary(rows: list[dict[str, Any]], summary_path: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("diagnostics"))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out.resolve()
    projects = discover_calibration_projects(root)
    if args.limit > 0:
        projects = projects[: args.limit]

    rows = [run_project(root, out_dir, project) for project in projects]
    write_summary(rows, out_dir / "summary.csv")

    completed = sum(1 for row in rows if row["ran_to_completion"] == "true")
    print(f"diagnostics summary: {completed}/{len(rows)} completed")
    print(out_dir / "summary.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
