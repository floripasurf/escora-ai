"""Tests for the pipeline_service helper layer (regeneration from revision)."""

from pathlib import Path
from unittest.mock import patch

from api.services import pipeline_service


def test_regenerate_from_revision_writes_validated_files(tmp_path: Path):
    """regenerate_from_revision must call process_dxf with output_suffix='_validated'."""
    captured = {}

    def fake_process_dxf(input_path, job_id, mode="price",
                         inventory_name=None, output_suffix="",
                         branch_id=None):
        captured["input_path"] = input_path
        captured["job_id"] = job_id
        captured["output_suffix"] = output_suffix
        stem = Path(input_path).stem
        return {
            "beam_count": 1,
            "pillar_count": 0,
            "slab_count": 0,
            "total_shores": 5,
            "beams": [],
            "slabs": [],
            "warnings": [],
            "output_dxf_path": f"/out/{stem}_escoras{output_suffix}.dxf",
            "csv_path": f"/out/{stem}_BOM{output_suffix}.csv",
            "ifc_path": f"/out/{stem}{output_suffix}.ifc",
            "relatorio": f"/out/{stem}_relatorio{output_suffix}.pdf",
            "memoria_calculo": f"/out/{stem}_memoria_calculo{output_suffix}.pdf",
            "orcamento": f"/out/{stem}_orcamento{output_suffix}.pdf",
        }

    with patch.object(pipeline_service, "process_dxf", side_effect=fake_process_dxf):
        result = pipeline_service.regenerate_from_revision(
            original_input_path="/input/proj.dxf",
            revised_input_path="/input/proj_revisado.dxf",
            job_id="abc123",
        )

    # Called with the revised file, not the original
    assert captured["input_path"] == "/input/proj_revisado.dxf"
    assert captured["job_id"] == "abc123"
    assert captured["output_suffix"] == "_validated"

    # All 6 expected paths use the _validated suffix
    assert result["output_dxf_path"].endswith("_validated.dxf")
    assert result["csv_path"].endswith("_validated.csv")
    assert result["ifc_path"].endswith("_validated.ifc")
    assert result["relatorio"].endswith("_validated.pdf")
    assert result["memoria_calculo"].endswith("_validated.pdf")
    assert result["orcamento"].endswith("_validated.pdf")
