import csv
import importlib.util
import subprocess
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "diagnose" / "run_all_calibration.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_all_calibration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CalibrationInventoryTests(unittest.TestCase):
    def test_discovers_12_supplier_calibration_projects(self):
        module = load_module()

        projects = module.discover_calibration_projects(ROOT)

        self.assertEqual(len(projects), 12)
        project_ids = {p.project_id for p in projects}
        self.assertIn("78579-12-PE-PAVTO-TIPO-TORRE-B-LT02-R00", project_ids)
        self.assertTrue(all(p.shoring_dxf.exists() for p in projects))

    def test_pairs_11_structural_reference_files(self):
        module = load_module()

        projects = module.discover_calibration_projects(ROOT)
        paired = [p for p in projects if p.structural_dxf is not None]

        self.assertEqual(len(paired), 11)
        self.assertTrue(all(p.structural_dxf.exists() for p in paired))

    def test_writes_summary_even_when_pipeline_dependencies_are_missing(self):
        out_dir = ROOT / "diagnostics" / "_unittest_inventory"
        if out_dir.exists():
            for child in sorted(out_dir.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            out_dir.rmdir()

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--root",
                str(ROOT),
                "--out",
                str(out_dir),
                "--limit",
                "1",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary_path = out_dir / "summary.csv"
        self.assertTrue(summary_path.exists())
        with summary_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 1)
        self.assertIn(rows[0]["ran_to_completion"], {"true", "false"})
        self.assertTrue(rows[0]["project_id"])

    def test_incremental_runner_preserves_completed_rows_when_later_project_fails(self):
        module = load_module()
        out_dir = ROOT / "diagnostics" / "_unittest_incremental"
        if out_dir.exists():
            for child in sorted(out_dir.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            out_dir.rmdir()

        projects = [
            module.CalibrationProject(
                project_id="FIRST",
                shoring_dxf=ROOT / "first.dxf",
                structural_dxf=None,
            ),
            module.CalibrationProject(
                project_id="SECOND",
                shoring_dxf=ROOT / "second.dxf",
                structural_dxf=None,
            ),
        ]

        def fake_runner(root, out_dir, project):
            if project.project_id == "SECOND":
                raise RuntimeError("boom")
            return {
                "project_id": project.project_id,
                "shoring_dxf": str(project.shoring_dxf),
                "structural_dxf": "",
                "ran_to_completion": "true",
                "bom_kg_total": "1.00",
                "kg_per_m3": "1.00",
                "tower_count": "",
                "telescopic_count": "1",
                "exceptions_count": "0",
                "error_type": "",
                "error_message": "",
                "output_dir": str(out_dir / "output" / project.project_id),
            }

        with self.assertRaises(RuntimeError):
            module.run_projects_incrementally(ROOT, out_dir, projects, fake_runner)

        summary_path = out_dir / "summary.csv"
        self.assertTrue(summary_path.exists())
        with summary_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual([row["project_id"] for row in rows], ["FIRST"])

    def test_incremental_runner_records_timeout_row_and_continues(self):
        module = load_module()
        out_dir = ROOT / "diagnostics" / "_unittest_timeout"
        if out_dir.exists():
            for child in sorted(out_dir.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            out_dir.rmdir()

        projects = [
            module.CalibrationProject(
                project_id="SLOW",
                shoring_dxf=ROOT / "slow.dxf",
                structural_dxf=None,
            ),
            module.CalibrationProject(
                project_id="FAST",
                shoring_dxf=ROOT / "fast.dxf",
                structural_dxf=None,
            ),
        ]

        def fake_runner(root, out_dir, project):
            if project.project_id == "SLOW":
                time.sleep(0.2)
            return {
                "project_id": project.project_id,
                "shoring_dxf": str(project.shoring_dxf),
                "structural_dxf": "",
                "ran_to_completion": "true",
                "bom_kg_total": "1.00",
                "kg_per_m3": "1.00",
                "tower_count": "",
                "telescopic_count": "1",
                "exceptions_count": "0",
                "error_type": "",
                "error_message": "",
                "output_dir": str(out_dir / "output" / project.project_id),
            }

        rows = module.run_projects_incrementally(
            ROOT,
            out_dir,
            projects,
            fake_runner,
            project_timeout_seconds=0.01,
        )

        self.assertEqual([row["project_id"] for row in rows], ["SLOW", "FAST"])
        self.assertEqual(rows[0]["ran_to_completion"], "false")
        self.assertEqual(rows[0]["error_type"], "TimeoutError")
        self.assertEqual(rows[0]["exceptions_count"], "1")
        self.assertEqual(rows[1]["ran_to_completion"], "true")


if __name__ == "__main__":
    unittest.main()
