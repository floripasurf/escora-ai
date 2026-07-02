PROJECT_PAYLOAD = {
    "floors": 1,
    "target_area_m2": 62,
    "bedrooms": 2,
    "bathrooms": 1,
    "layout_type": "open_kitchen",
    "has_garage": False,
    "lot_width_m": 8,
    "lot_depth_m": 20,
    "block_size": "14",
    "region": "sudeste",
    "soil_capacity_kpa": 100,
    "ceiling_height_m": 2.8,
    "roof_type": "wooden_truss",
}


def test_project_create_requires_authenticated_branch(client_unauth, monkeypatch):
    from api.routes import projects as projects_route

    def fake_process_project(input_data, project_id, output_dir):
        return {"status": "done", "project_id": project_id}

    monkeypatch.setattr(projects_route, "process_project", fake_process_project)

    response = client_unauth.post("/api/v1/projects", json=PROJECT_PAYLOAD)

    assert response.status_code == 401


def test_project_status_is_tenant_scoped(client, client_b, monkeypatch):
    from api.routes import projects as projects_route

    def fake_process_project(input_data, project_id, output_dir):
        return {
            "status": "done",
            "project_id": project_id,
            "summary": {"total_area_m2": input_data["target_area_m2"]},
            "preview": {"rooms": []},
        }

    monkeypatch.setattr(projects_route, "process_project", fake_process_project)

    created = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    owner_status = client.get(f"/api/v1/projects/{project_id}/status")
    other_tenant_status = client_b.get(f"/api/v1/projects/{project_id}/status")

    assert owner_status.status_code == 200, owner_status.text
    assert other_tenant_status.status_code == 404


def test_project_records_survive_process_memory_loss(client, monkeypatch):
    from api.routes import projects as projects_route
    from api.services import project_service

    def fake_process_project(input_data, project_id, output_dir):
        return {
            "status": "done",
            "project_id": project_id,
            "summary": {"total_area_m2": input_data["target_area_m2"]},
            "preview": {"rooms": []},
        }

    monkeypatch.setattr(projects_route, "process_project", fake_process_project)

    created = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    project_service.clear_memory_cache_for_tests()

    response = client.get(f"/api/v1/projects/{project_id}/status")

    assert response.status_code == 200, response.text
    assert response.json()["summary"] == {"total_area_m2": 62}


def test_project_downloads_require_owner_branch(client_unauth, client, monkeypatch, tmp_path):
    from api.routes import projects as projects_route

    dxf_path = tmp_path / "projeto.dxf"
    dxf_path.write_text("0\nEOF\n")

    def fake_process_project(input_data, project_id, output_dir):
        return {
            "status": "done",
            "project_id": project_id,
            "arch_dxf_path": str(dxf_path),
            "summary": {},
            "preview": {"rooms": []},
        }

    monkeypatch.setattr(projects_route, "process_project", fake_process_project)

    created = client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    response = client_unauth.get(f"/api/v1/projects/{project_id}/download/dxf/arch")

    assert response.status_code == 401
