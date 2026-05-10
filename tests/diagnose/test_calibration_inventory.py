import csv
import importlib.util
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
