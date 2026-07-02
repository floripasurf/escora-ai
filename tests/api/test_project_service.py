"""Sprint 3: persistência de projects em SQLite (mata o _project_store dict).

Antes, projetos de alvenaria viviam num dict em memória — sumiam a cada
`launchctl kickstart` e não tinham escopo de tenant.
"""
import pytest

from api.services import project_service

FAKE_RESULT = {
    "status": "done",
    "summary": {"area_m2": 50},
    "preview": {"rooms": []},
    "arch_dxf_path": None,
    "struct_dxf_path": None,
}

PROJECT_PAYLOAD = {
    "target_area_m2": 50.0,
    "bedrooms": 2,
    "lot_width_m": 10.0,
    "lot_depth_m": 20.0,
}


@pytest.fixture
def fake_process_project(monkeypatch):
    def _fake(input_data, project_id, output_dir):
        return dict(FAKE_RESULT)
    monkeypatch.setattr("api.routes.projects.process_project", _fake)


def test_project_survives_module_state(client, fake_process_project):
    """O estado vive no SQLite, não em memória — releitura direta funciona."""
    r = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    assert r.status_code == 201
    project_id = r.json()["id"]

    # Leitura direta do serviço (sem passar pela rota): dados persistidos.
    stored = project_service.get_project(project_id)
    assert stored is not None
    assert stored["status"] == "done"
    assert stored["branch_id"] == "test-a"
    assert stored["summary"] == {"area_m2": 50}
    assert stored["input_data"]["bedrooms"] == 2


def test_status_reads_persisted_result(client, fake_process_project):
    r = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    project_id = r.json()["id"]
    s = client.get(f"/api/v1/projects/{project_id}/status")
    assert s.status_code == 200
    body = s.json()
    assert body["status"] == "done"
    assert body["summary"] == {"area_m2": 50}


def test_sweep_orphan_processing():
    p = project_service.create_project("test-a", {"bedrooms": 2})
    assert p["status"] == "processing"

    swept = project_service.sweep_orphan_processing()
    assert swept == 1
    after = project_service.get_project(p["id"])
    assert after["status"] == "error"
    assert "reinicio" in after["error"]


def test_worker_error_persisted(client, monkeypatch):
    def _boom(input_data, project_id, output_dir):
        raise RuntimeError("layout impossível")
    monkeypatch.setattr("api.routes.projects.process_project", _boom)

    r = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    project_id = r.json()["id"]
    s = client.get(f"/api/v1/projects/{project_id}/status")
    assert s.json()["status"] == "error"
    assert "layout impossível" in s.json()["error"]


def test_cross_tenant_isolation(client, client_b, fake_process_project):
    r = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    project_id = r.json()["id"]
    assert client.get(f"/api/v1/projects/{project_id}/status").status_code == 200
    assert client_b.get(f"/api/v1/projects/{project_id}/status").status_code == 404
    # E via serviço, com branch errada:
    assert project_service.get_project(project_id, branch_id="test-b") is None
