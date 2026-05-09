"""Regression test fixtures — discovers all DXFs for parameterized testing."""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

INPUT_DIRS = [
    ROOT / "input" / "supplier_estrutural",
    ROOT / "input" / "Sergio1",
]


def _discover_dxfs():
    """Find all DXF files in input directories."""
    dxfs = []
    for d in INPUT_DIRS:
        if d.exists():
            dxfs.extend(sorted(d.glob("*.dxf")))
    return dxfs


_ALL_DXFS = _discover_dxfs()


def _project_id(dxf_path: Path) -> str:
    parts = dxf_path.stem.split("-")
    return parts[0].strip() if parts else dxf_path.stem[:20]


@pytest.fixture(
    params=[pytest.param(p, id=_project_id(p)) for p in _ALL_DXFS],
)
def calibration_dxf(request):
    """Yields (project_id, dxf_path) for each discovered DXF."""
    dxf_path = request.param
    return _project_id(dxf_path), dxf_path
