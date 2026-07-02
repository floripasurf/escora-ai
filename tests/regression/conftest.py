"""Regression test fixtures — discovers all DXFs for parameterized testing.

Discovery covers the local calibration inputs (gitignored — only present on
dev machines) AND the committed fixtures in tests/fixtures, so the suite
always collects >0 items in CI. If nothing is found, collection FAILS loudly
instead of passing on an empty parameter set (which silently disabled the
whole regression suite until 2026-07).
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

INPUT_DIRS = [
    ROOT / "input" / "orguel_estrutural",
    ROOT / "input" / "Sergio1",
    ROOT / "tests" / "fixtures",
]


def _discover_dxfs():
    """Find all DXF files in input directories (case-insensitive suffix)."""
    dxfs = []
    for d in INPUT_DIRS:
        if d.exists():
            dxfs.extend(sorted(
                p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() == ".dxf"
            ))
    return dxfs


_ALL_DXFS = _discover_dxfs()

if not _ALL_DXFS:
    raise RuntimeError(
        "Nenhum DXF de regressão encontrado — nem inputs locais nem "
        "tests/fixtures/*.DXF. A suíte de regressão não pode passar vazia."
    )


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
