"""Sprint 1 security hardening: auth on alvenaria routes, upload filename
sanitization, inventory import cap, login rate limit, drawing tempfile cleanup."""

import os
from pathlib import Path

import ezdxf
import pytest

from api.services.storage import sanitize_filename


# --- sanitize_filename (unit) ---

def test_sanitize_strips_path_traversal():
    assert sanitize_filename("../../etc/passwd.dxf") == "passwd.dxf"
    assert sanitize_filename("..\\..\\x.dxf") == "x.dxf"
    assert sanitize_filename("/abs/path/plan.DXF") == "plan.dxf"


def test_sanitize_normalizes_weird_chars():
    assert sanitize_filename("plano térreo (v2).dxf") == "plano_t_rreo_v2.dxf"
    assert sanitize_filename("...") == "upload.dxf"
    assert sanitize_filename("") == "upload.dxf"
    assert sanitize_filename(None) == "upload.dxf"


def test_sanitize_keeps_clean_names():
    assert sanitize_filename("CFL-SUB_v3.dxf") == "CFL-SUB_v3.dxf"


# --- upload path stays inside the job dir (API) ---

def _tiny_dxf(tmp_path):
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "tiny.dxf"
    doc.saveas(str(path))
    return path


def test_upload_traversal_lands_inside_job_dir(client, tmp_path):
    path = _tiny_dxf(tmp_path)
    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/jobs",
            files={"file": ("../../evil.dxf", f, "application/octet-stream")},
        )
    assert r.status_code == 201
    job_id = r.json()["id"]

    data_dir = Path(os.environ["ESCORA_DATA_DIR"])
    job_dir = data_dir / "uploads" / job_id
    assert (job_dir / "evil.dxf").exists()
    # Nothing escaped the uploads tree.
    assert not (data_dir / "evil.dxf").exists()
    assert not (data_dir.parent / "evil.dxf").exists()


# --- auth required on projects/design/drawing ---

FAKE_PROJECT_RESULT = {"status": "done", "summary": {"area_m2": 50}}


@pytest.fixture
def fake_process_project(monkeypatch):
    def _fake(input_data, project_id, output_dir):
        return {**FAKE_PROJECT_RESULT, "project_id": project_id}
    monkeypatch.setattr("api.routes.projects.process_project", _fake)


PROJECT_PAYLOAD = {
    "target_area_m2": 50.0,
    "bedrooms": 2,
    "lot_width_m": 10.0,
    "lot_depth_m": 20.0,
}


def test_projects_requires_auth(client_unauth):
    r = client_unauth.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    assert r.status_code == 401
    r = client_unauth.get("/api/v1/projects/abc123/status")
    assert r.status_code == 401


def test_design_requires_auth(client_unauth):
    r = client_unauth.post("/api/v1/design/preview", json=PROJECT_PAYLOAD)
    assert r.status_code == 401
    r = client_unauth.post("/api/v1/design/alternatives", json=PROJECT_PAYLOAD)
    assert r.status_code == 401


def test_drawing_requires_auth(client_unauth):
    r = client_unauth.post("/api/v1/drawing/floor-plan", json={"walls": []})
    assert r.status_code == 401
    r = client_unauth.get("/api/v1/drawing/formats")
    assert r.status_code == 401


def test_projects_cross_tenant_404(client, client_b, fake_process_project):
    r = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    assert r.status_code == 201
    project_id = r.json()["id"]

    # Owner branch sees it…
    r = client.get(f"/api/v1/projects/{project_id}/status")
    assert r.status_code == 200

    # …the other locadora gets 404, indistinguishable from nonexistent.
    r = client_b.get(f"/api/v1/projects/{project_id}/status")
    assert r.status_code == 404


def test_project_ids_are_not_guessable(client, fake_process_project):
    r = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    assert len(r.json()["id"]) == 32  # full uuid4 hex, not a 8-char prefix


# --- inventory import cap ---

def test_inventory_import_over_cap_returns_413(client, monkeypatch):
    import api.routes.inventory as inv
    monkeypatch.setattr(inv, "IMPORT_MAX_BYTES", 1024)
    big = b"secao,item,qtd\n" + b"x" * 2048
    r = client.post(
        "/api/v1/inventory/import-preview",
        files={"file": ("estoque.csv", big, "text/csv")},
    )
    assert r.status_code == 413


# --- login/signup rate limit ---

def test_login_rate_limited(client_unauth, monkeypatch):
    monkeypatch.delenv("ESCORA_RATE_LIMIT_DISABLED", raising=False)
    from api import ratelimit
    ratelimit.reset()

    for _ in range(5):
        r = client_unauth.post(
            "/api/v1/auth/login",
            json={"username": "nobody@x.com", "password": "wrong"},
        )
        assert r.status_code == 401
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "nobody@x.com", "password": "wrong"},
    )
    assert r.status_code == 429
    ratelimit.reset()


# --- drawing tempfile cleanup ---

def test_drawing_floor_plan_cleans_tempfile(client, tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    r = client.post(
        "/api/v1/drawing/floor-plan",
        json={
            "walls": [
                {"x1": 0, "y1": 0, "x2": 5, "y2": 0},
                {"x1": 5, "y1": 0, "x2": 5, "y2": 4},
            ]
        },
    )
    assert r.status_code == 200
    assert r.content[:6] != b""  # got a DXF body back
    leftovers = list(Path(tmp_path).glob("*.dxf"))
    assert leftovers == []
