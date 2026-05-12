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
import signal
import sys
import traceback
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
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
    "supplier_support_count",
    "generated_support_count",
    "support_count_delta",
    "support_count_ratio",
    "exceptions_count",
    "error_type",
    "error_message",
    "output_dir",
]

SUPPORT_LAYER_PREFIXES = ("ESC", "TORRE", "TWR", "VM", "ALU")


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


def _is_support_entity(entity: Any) -> bool:
    layer = getattr(entity.dxf, "layer", "").upper()
    if layer.startswith(SUPPORT_LAYER_PREFIXES):
        return True
    if entity.dxftype() != "INSERT":
        return False
    name = getattr(entity.dxf, "name", "").upper()
    return name.startswith(SUPPORT_LAYER_PREFIXES)


def count_support_entities(dxf_path: Path | str | None) -> int | None:
    """Count shoring-related DXF entities using Supplier/Escora layer names."""
    if not dxf_path:
        return None
    path = Path(dxf_path)
    if not path.exists():
        return None
    try:
        import ezdxf

        doc = ezdxf.readfile(path)
        return sum(1 for entity in doc.modelspace() if _is_support_entity(entity))
    except Exception:
        return None


def _first_generated_dxf(output_dir: Path) -> Path | None:
    generated = sorted(output_dir.glob("*_escoras.dxf"))
    return generated[0] if generated else None


def _format_optional_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _support_delta(supplier_count: int | None, generated_count: int | None) -> str:
    if supplier_count is None or generated_count is None:
        return ""
    return str(generated_count - supplier_count)


def _support_ratio(supplier_count: int | None, generated_count: int | None) -> str:
    if supplier_count is None or generated_count is None or supplier_count == 0:
        return ""
    return f"{generated_count / supplier_count:.2f}"


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
        "supplier_support_count": "",
        "generated_support_count": "",
        "support_count_delta": "",
        "support_count_ratio": "",
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
        generated_output_dir = out_dir / "output" / project.project_id
        supplier_support_count = count_support_entities(project.shoring_dxf)
        generated_support_count = count_support_entities(
            _first_generated_dxf(generated_output_dir)
        )
        row["supplier_support_count"] = _format_optional_int(supplier_support_count)
        row["generated_support_count"] = _format_optional_int(generated_support_count)
        row["support_count_delta"] = _support_delta(
            supplier_support_count,
            generated_support_count,
        )
        row["support_count_ratio"] = _support_ratio(
            supplier_support_count,
            generated_support_count,
        )
        row["output_dir"] = str(generated_output_dir)
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


@contextmanager
def project_timeout(seconds: float):
    if seconds <= 0:
        yield
        return

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, 0)

    def raise_timeout(signum: int, frame: FrameType | None) -> None:
        raise TimeoutError(f"project exceeded timeout of {seconds:g}s")

    signal.signal(signal.SIGALRM, raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def timeout_row(out_dir: Path, project: CalibrationProject, exc: TimeoutError) -> dict[str, Any]:
    project_dir = out_dir / project.project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    error_message = str(exc)
    (project_dir / "errors.log").write_text(error_message + "\n", encoding="utf-8")
    return {
        "project_id": project.project_id,
        "shoring_dxf": str(project.shoring_dxf),
        "structural_dxf": str(project.structural_dxf or ""),
        "ran_to_completion": "false",
        "bom_kg_total": "",
        "kg_per_m3": "",
        "tower_count": "",
        "telescopic_count": "",
        "supplier_support_count": "",
        "generated_support_count": "",
        "support_count_delta": "",
        "support_count_ratio": "",
        "exceptions_count": "1",
        "error_type": "TimeoutError",
        "error_message": error_message,
        "output_dir": str(project_dir),
    }


def run_projects_incrementally(
    root: Path,
    out_dir: Path,
    projects: list[CalibrationProject],
    runner: Any = run_project,
    project_timeout_seconds: float = 0,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    summary_path = out_dir / "summary.csv"
    write_summary(rows, summary_path)
    for project in projects:
        try:
            with project_timeout(project_timeout_seconds):
                row = runner(root, out_dir, project)
        except TimeoutError as exc:
            row = timeout_row(out_dir, project, exc)
        rows.append(row)
        write_summary(rows, summary_path)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("diagnostics"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--project-timeout",
        type=float,
        default=0,
        help="Seconds before a single project is marked as timed out; 0 disables.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out.resolve()
    projects = discover_calibration_projects(root)
    if args.limit > 0:
        projects = projects[: args.limit]

    rows = run_projects_incrementally(
        root,
        out_dir,
        projects,
        project_timeout_seconds=args.project_timeout,
    )

    completed = sum(1 for row in rows if row["ran_to_completion"] == "true")
    print(f"diagnostics summary: {completed}/{len(rows)} completed")
    print(out_dir / "summary.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
