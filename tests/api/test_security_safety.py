from pathlib import Path

from api.services.storage import save_upload, safe_upload_filename


def test_safe_upload_filename_strips_path_traversal():
    assert safe_upload_filename("../evil.dxf") == "evil.dxf"
    assert safe_upload_filename("..\\evil.dxf") == ".._evil.dxf"


def test_save_upload_stays_inside_job_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ESCORA_DATA_DIR", str(tmp_path))

    saved = Path(save_upload(b"payload", "../evil.dxf", "job-1"))

    assert saved == tmp_path / "uploads" / "job-1" / "evil.dxf"
    assert saved.read_bytes() == b"payload"
    assert not (tmp_path / "uploads" / "evil.dxf").exists()


def test_projects_require_auth(client_unauth):
    response = client_unauth.post(
        "/api/v1/projects",
        json={
            "target_area_m2": 60,
            "bedrooms": 2,
            "lot_width_m": 8,
            "lot_depth_m": 20,
        },
    )

    assert response.status_code == 401


def test_design_and_drawing_require_auth(client_unauth):
    design_response = client_unauth.post(
        "/api/v1/design/alternatives",
        json={
            "target_area_m2": 60,
            "bedrooms": 2,
            "lot_width_m": 8,
            "lot_depth_m": 20,
        },
    )
    drawing_response = client_unauth.post(
        "/api/v1/drawing/floor-plan",
        json={"walls": [], "format": "A2", "scale": "1:50"},
    )

    assert design_response.status_code == 401
    assert drawing_response.status_code == 401


def test_projects_use_full_uuid_and_branch_scope(client, client_b, monkeypatch):
    def fake_process_project(input_data, project_id, output_dir):
        return {
            "status": "done",
            "project_id": project_id,
            "summary": {"area_m2": input_data["target_area_m2"]},
            "preview": {"rooms": []},
        }

    monkeypatch.setattr("api.routes.projects.process_project", fake_process_project)

    response = client.post(
        "/api/v1/projects",
        json={
            "target_area_m2": 60,
            "bedrooms": 2,
            "lot_width_m": 8,
            "lot_depth_m": 20,
        },
    )

    assert response.status_code == 201
    project_id = response.json()["id"]
    assert len(project_id) == 36
    assert client.get(f"/api/v1/projects/{project_id}/status").status_code == 200
    assert client_b.get(f"/api/v1/projects/{project_id}/status").status_code == 404


def test_auth_rate_limit_blocks_after_configured_attempts(client_unauth, monkeypatch):
    monkeypatch.setenv("ESCORA_LOGIN_RATE_LIMIT_MAX", "2")
    monkeypatch.setenv("ESCORA_LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60")

    payload = {"username": "ghost@example.com", "password": "wrong"}
    assert client_unauth.post("/api/v1/auth/login", json=payload).status_code == 401
    assert client_unauth.post("/api/v1/auth/login", json=payload).status_code == 401
    assert client_unauth.post("/api/v1/auth/login", json=payload).status_code == 429


def test_cors_and_csp_headers(client_unauth):
    response = client_unauth.options(
        "/api/v1/health",
        headers={
            "Origin": "https://estrutura.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://estrutura.app"

    health = client_unauth.get("/api/v1/health")
    assert "Content-Security-Policy" in health.headers
    assert "frame-ancestors 'none'" in health.headers["Content-Security-Policy"]
