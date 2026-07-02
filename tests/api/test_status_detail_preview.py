"""Sprint 4: progresso por estágio (status_detail) + preview 2D no job."""
import ezdxf

from api.services import job_service
from api.services.pipeline_service import (
    PREVIEW_MAX_SHORES,
    _build_shoring_preview,
    _set_status_detail,
)


def _make_job(branch_id="test-a"):
    return job_service.create_job("plan.dxf", "/tmp/x.dxf", branch_id=branch_id)


def test_status_detail_written_and_exposed(client, tmp_path):
    job = _make_job()
    _set_status_detail(job["id"], "", "Gerando o DXF de escoramento")

    stored = job_service.get_job(job["id"])
    assert stored["status_detail"] == "Gerando o DXF de escoramento"

    r = client.get(f"/api/v1/jobs/{job['id']}/status")
    assert r.status_code == 200
    assert r.json()["status_detail"] == "Gerando o DXF de escoramento"


def test_status_detail_skipped_for_revision_regen():
    job = _make_job()
    _set_status_detail(job["id"], "_validated", "não deve gravar")
    assert job_service.get_job(job["id"])["status_detail"] is None


def test_status_detail_column_migrates_existing_db(tmp_path, monkeypatch):
    """DB antigo sem a coluna ganha o ALTER idempotente no init_db."""
    import sqlite3
    monkeypatch.setenv("ESCORA_DATA_DIR", str(tmp_path))
    db = tmp_path / "jobs.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE jobs (id TEXT PRIMARY KEY, branch_id TEXT NOT NULL, "
        "status TEXT NOT NULL, filename TEXT NOT NULL, created_at TEXT NOT NULL, "
        "updated_at TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()

    job_service.init_db()
    job_service.init_db()  # idempotente

    cols = {
        r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(jobs)")
    }
    assert "status_detail" in cols


class _Shore:
    def __init__(self, x, y, shore_type="telescopic"):
        self.x, self.y, self.shore_type = x, y, shore_type


class _SlabResult:
    def __init__(self, polygon, shores):
        self.polygon = polygon
        self.shores = shores


class _Calc:
    def __init__(self, slab_results, beam_results=()):
        self.slab_results = list(slab_results)
        self.beam_results = list(beam_results)


def test_build_preview_geometry():
    from shapely.geometry import box
    calc = _Calc([_SlabResult(box(0, 0, 10, 8),
                              [_Shore(1, 1), _Shore(2, 2, "tower")])])
    preview = _build_shoring_preview(calc)
    assert preview is not None
    assert preview["bbox"] == [0.0, 0.0, 10.0, 8.0]
    assert preview["truncated"] is False
    assert len(preview["slabs"]) == 1
    assert preview["slabs"][0]["shores"] == [
        [1.0, 1.0, "telescopic"], [2.0, 2.0, "tower"],
    ]


def test_build_preview_caps_shores():
    from shapely.geometry import box
    shores = [_Shore(i * 0.1, 0.0) for i in range(PREVIEW_MAX_SHORES + 10)]
    calc = _Calc([_SlabResult(box(0, 0, 400, 5), shores)])
    preview = _build_shoring_preview(calc)
    assert preview["truncated"] is True
    assert len(preview["slabs"][0]["shores"]) == PREVIEW_MAX_SHORES


def test_build_preview_none_on_empty():
    assert _build_shoring_preview(None) is None
    assert _build_shoring_preview(_Calc([])) is None
