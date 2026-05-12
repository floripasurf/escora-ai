import csv
import importlib.util
import subprocess
import sys
import time
import unittest
import tempfile
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
        self.assertIn("supplier_support_count", rows[0])
        self.assertIn("generated_support_count", rows[0])
        self.assertIn("support_count_delta", rows[0])
        self.assertIn("support_count_ratio", rows[0])

    def test_counts_physical_support_entities_without_distribution_beams(self):
        if importlib.util.find_spec("ezdxf") is None:
            self.skipTest("ezdxf unavailable")

        import ezdxf

        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            dxf_path = Path(tmp) / "supports.dxf"
            doc = ezdxf.new("R2010")
            doc.blocks.new(name="ESC310_TEST")
            doc.blocks.new(name="TWR-TEST")
            msp = doc.modelspace()
            msp.add_circle((0, 0), radius=0.1, dxfattribs={"layer": "ESC310_Laje"})
            msp.add_line((0, 0), (1, 0), dxfattribs={"layer": "VM50_Viga"})
            msp.add_lwpolyline(
                [(0, 0), (1, 0), (1, 1), (0, 1)],
                close=True,
                dxfattribs={"layer": "ESC450_Laje"},
            )
            msp.add_blockref("TWR-TEST", (1, 1), dxfattribs={"layer": "0"})
            msp.add_blockref("IGNORED", (2, 2), dxfattribs={"layer": "Cotas"})
            msp.add_line((0, 0), (0, 1), dxfattribs={"layer": "Cotas"})
            doc.saveas(dxf_path)

            self.assertEqual(module.count_support_entities(dxf_path), 2)

    def test_breaks_supplier_support_entities_down_by_layer_semantics(self):
        if importlib.util.find_spec("ezdxf") is None:
            self.skipTest("ezdxf unavailable")

        import ezdxf

        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            dxf_path = Path(tmp) / "supports.dxf"
            doc = ezdxf.new("R2010")
            doc.blocks.new(name="ESC450-REESC")
            doc.blocks.new(name="1001550")
            doc.blocks.new(name="TWR-TEST")
            msp = doc.modelspace()
            msp.add_blockref("ESC450-REESC", (0, 0), dxfattribs={"layer": "ESC450_Laje"})
            msp.add_blockref("ESC450-REESC", (1, 0), dxfattribs={"layer": "ESC310_Viga"})
            msp.add_blockref("1001550", (2, 0), dxfattribs={"layer": "TORRE_LAJE"})
            msp.add_blockref("1001550", (3, 0), dxfattribs={"layer": "TORRE_VIGA"})
            msp.add_blockref("TWR-TEST", (4, 0), dxfattribs={"layer": "0"})
            msp.add_blockref("IGNORED", (5, 0), dxfattribs={"layer": "Cotas"})
            doc.saveas(dxf_path)

            breakdown = module.count_support_breakdown(dxf_path)

        self.assertEqual(
            breakdown,
            {
                "total": 5,
                "beam": 2,
                "slab": 2,
                "tower": 3,
                "telescopic": 2,
                "uncategorized": 1,
            },
        )

    def test_reads_generated_support_breakdown_from_bom_csv(self):
        module = load_module()

        with tempfile.TemporaryDirectory() as tmp:
            bom_path = Path(tmp) / "bom.csv"
            bom_path.write_text(
                "\ufeffTipo;Elemento;Comprimento (m);Secao (cm);Qtd Escoras;Espacamento (m);Regra\n"
                "Viga;V1;2.0;20x40;3;1.0;rule\n"
                "Laje;Laje 1;10.0;e=12cm;8;1.2x1.2;rule\n"
                "Acessório;Cruzeta;;;;;\n"
                "TOTAL;;;;11;;\n",
                encoding="utf-8",
            )

            breakdown = module.read_generated_bom_support_breakdown(bom_path)

        self.assertEqual(breakdown, {"beam": 3, "slab": 8, "total": 11})

    def test_generated_support_count_uses_pipeline_total_not_dxf_drawing_entities(self):
        module = load_module()

        self.assertEqual(
            module._generated_support_count(
                {"total_shores": 12},
                generated_dxf_support_count=48,
            ),
            12,
        )

    def test_support_count_delta_and_ratio_are_formatted_for_summary(self):
        module = load_module()

        self.assertEqual(module._support_delta(10, 14), "4")
        self.assertEqual(module._support_ratio(10, 14), "1.40")
        self.assertEqual(module._support_delta(None, 14), "")
        self.assertEqual(module._support_ratio(0, 14), "")

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
