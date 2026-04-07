"""Tests for revision-feedback features added to LearningStore."""

from datetime import datetime
from pathlib import Path

import pytest

from src.pipeline.learning_store import LearningStore, LearningRecord


def _make_record(filename: str, total_shores: int = 100) -> LearningRecord:
    return LearningRecord(
        filename=filename,
        timestamp=datetime.now().isoformat(),
        scale=1.0,
        beam_count=5,
        pillar_count=4,
        slab_count=2,
        total_shores=total_shores,
        is_valid=True,
    )


@pytest.fixture
def store(tmp_path: Path) -> LearningStore:
    s = LearningStore(path=tmp_path / "learning.json")
    return s


def test_revision_signal_persists(store: LearningStore, tmp_path: Path):
    rec = _make_record("PROJ.DXF", total_shores=100)
    store.add(rec)

    diff = {
        "beam_added": 8,
        "beam_removed": 2,
        "slab_added": 3,
        "slab_removed": 0,
        "beam_moved": 1,
        "accuracy_beam": 92.5,
        "accuracy_slab": 88.0,
    }
    store.update_record_with_revision(filename="PROJ.DXF", diff=diff)
    store.save()

    reloaded = LearningStore(path=tmp_path / "learning.json")
    rec2 = reloaded.get_file_stats("PROJ.DXF")
    assert rec2 is not None
    assert rec2.revision_uploaded is True
    assert rec2.revision_beam_shore_delta == 6   # 8 - 2
    assert rec2.revision_slab_shore_delta == 3
    assert rec2.revision_beam_match_rate == pytest.approx(0.925)
    assert rec2.revision_slab_match_rate == pytest.approx(0.88)
    assert rec2.revision_avg_position_error_m == pytest.approx(0.10)
    assert rec2.revision_added_layers.get("ESCORAS_VIGA") == 8
    assert rec2.revision_added_layers.get("ESCORAS_LAJE") == 3
    assert rec2.revision_removed_layers.get("ESCORAS_VIGA") == 2


def test_density_correction_clamped_high(store: LearningStore):
    """Engineer adds way more shores → ratio clamped to 1.5."""
    rec = _make_record("HIGH.DXF", total_shores=100)
    store.add(rec)
    diff = {
        "beam_added": 200, "beam_removed": 0,
        "slab_added": 100, "slab_removed": 0,
        "beam_moved": 0, "accuracy_beam": 0.0, "accuracy_slab": 0.0,
    }
    store.update_record_with_revision("HIGH.DXF", diff)
    assert store.get_shore_density_correction() == pytest.approx(1.5)


def test_density_correction_clamped_low(store: LearningStore):
    """Engineer removes most shores → ratio clamped to 0.7."""
    rec = _make_record("LOW.DXF", total_shores=100)
    store.add(rec)
    diff = {
        "beam_added": 0, "beam_removed": 80,
        "slab_added": 0, "slab_removed": 50,
        "beam_moved": 0, "accuracy_beam": 0.0, "accuracy_slab": 0.0,
    }
    store.update_record_with_revision("LOW.DXF", diff)
    assert store.get_shore_density_correction() == pytest.approx(0.7)


def test_density_correction_default_when_no_revisions(store: LearningStore):
    rec = _make_record("NOREV.DXF", total_shores=50)
    store.add(rec)
    assert store.get_shore_density_correction() == 1.0


def test_density_correction_in_range(store: LearningStore):
    rec = _make_record("MID.DXF", total_shores=100)
    store.add(rec)
    diff = {
        "beam_added": 5, "beam_removed": 0,
        "slab_added": 5, "slab_removed": 0,
        "beam_moved": 0, "accuracy_beam": 0.0, "accuracy_slab": 0.0,
    }
    store.update_record_with_revision("MID.DXF", diff)
    correction = store.get_shore_density_correction()
    assert correction == pytest.approx(1.10)
    assert 0.7 <= correction <= 1.5


def test_validated_layer_map_promotes_human_layers(store: LearningStore):
    rec = _make_record("LAYERS.DXF", total_shores=100)
    store.add(rec)
    diff = {
        "beam_added": 4, "beam_removed": 0,
        "slab_added": 2, "slab_removed": 0,
        "beam_moved": 0, "accuracy_beam": 0.0, "accuracy_slab": 0.0,
    }
    store.update_record_with_revision("LAYERS.DXF", diff)
    layer_map = store.get_validated_layer_map()
    assert layer_map.get("ESCORAS_VIGA") == "beam"
    assert layer_map.get("ESCORAS_LAJE") == "slab"


def test_update_revision_unknown_filename_is_noop(store: LearningStore):
    store.update_record_with_revision("MISSING.DXF", {"beam_added": 1})
    assert store.get_shore_density_correction() == 1.0


def test_branch_scoped_stores_are_isolated(tmp_path: Path, monkeypatch):
    """Revisions in branch A must not bias density correction in branch B."""
    # Redirect the per-branch directory into tmp_path
    import src.pipeline.learning_store as ls_mod
    monkeypatch.setattr(ls_mod, "BRANCH_STORE_DIR", tmp_path / "learning")

    store_a = LearningStore(branch_id="branch-a")
    store_b = LearningStore(branch_id="branch-b")

    rec = _make_record("SHARED.DXF", total_shores=100)
    store_a.add(rec)
    store_a.update_record_with_revision("SHARED.DXF", {
        "beam_added": 30, "beam_removed": 0,
        "slab_added": 0, "slab_removed": 0,
        "beam_moved": 0, "accuracy_beam": 0.0, "accuracy_slab": 0.0,
    })
    store_a.save()

    assert store_a.get_shore_density_correction() > 1.0

    # Branch B is untouched
    store_b_fresh = LearningStore(branch_id="branch-b")
    assert store_b_fresh.get_shore_density_correction() == 1.0
    assert store_b_fresh.run_count == 0

    # Different on-disk files
    assert store_a.path != store_b.path
    assert store_a.path.exists()
