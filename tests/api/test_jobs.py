import ezdxf


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200


def test_sanitize_diagnostics_drops_legacy_and_unknown_keys():
    # Compat (codex): jobs antigos têm chaves legadas (ex.: vertical_kg_m2 antes
    # da renomeação). Com extra='forbid' no schema, passá-las quebraria o status.
    # O sanitizador dropa o que não é campo conhecido → endpoint não quebra.
    from api.routes.jobs import _sanitize_diagnostics
    from api.models.schemas import DiagnosticsData
    raw = {"vertical_kg_m3": 4.0, "vertical_kg_m2": 9.0, "legacy_x": 1}
    out = _sanitize_diagnostics(raw)
    assert out["vertical_kg_m3"] == 4.0
    assert "vertical_kg_m2" not in out and "legacy_x" not in out
    DiagnosticsData(**out)  # não levanta (forbid satisfeito)


def test_sanitize_diagnostics_none_safe():
    from api.routes.jobs import _sanitize_diagnostics
    assert _sanitize_diagnostics(None) == {}


def test_upload_dxf(client, tmp_path):
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "test.dxf"
    doc.saveas(str(path))

    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/jobs",
            files={"file": ("test.dxf", f, "application/octet-stream")},
        )
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["status"] in ("pending", "processing")


def test_get_job_status(client, tmp_path):
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "test.dxf"
    doc.saveas(str(path))

    with open(path, "rb") as f:
        r = client.post("/api/v1/jobs", files={"file": ("test.dxf", f, "application/octet-stream")})
    job_id = r.json()["id"]

    r = client.get(f"/api/v1/jobs/{job_id}/status")
    assert r.status_code == 200
    assert r.json()["status"] in ("pending", "processing", "completed", "error")


def test_get_job_status_sweeps_stale_processing(client, tmp_path, monkeypatch):
    from api.routes import jobs as jobs_route

    calls = {"count": 0}

    def fake_sweep():
        calls["count"] += 1
        return 0

    monkeypatch.setattr(jobs_route.job_service, "sweep_stale_processing", fake_sweep)

    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "test.dxf"
    doc.saveas(str(path))

    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/jobs",
            files={"file": ("test.dxf", f, "application/octet-stream")},
        )
    job_id = r.json()["id"]

    r = client.get(f"/api/v1/jobs/{job_id}/status")

    assert r.status_code == 200
    assert calls["count"] == 1
