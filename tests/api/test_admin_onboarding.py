"""Admin onboarding and role permission tests."""

from fastapi.testclient import TestClient


def _login(username: str, password: str, branch_id: str) -> TestClient:
    from api.main import app

    tc = TestClient(app)
    r = tc.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    tc.headers.update(
        {
            "Authorization": f"Bearer {r.json()['token']}",
            "X-Branch-Id": branch_id,
        }
    )
    return tc


def test_owner_can_manage_locadora_branches_and_users(client):
    loc = client.get("/api/v1/admin/locadora")
    assert loc.status_code == 200
    assert loc.json()["id"] == "loc-a"
    assert loc.json()["users"][0]["role"] == "owner"

    branch = client.post(
        "/api/v1/admin/branches",
        json={"branch_name": "Filial Norte", "inventory_name": "filial_norte"},
    )
    assert branch.status_code == 200
    assert branch.json()["branch_name"] == "Filial Norte"
    assert branch.json()["inventory_name"] == "filial_norte"

    user = client.post(
        "/api/v1/admin/users",
        json={
            "username": "operador@example.com",
            "name": "Operador",
            "password": "senha123",
            "role": "operator",
        },
    )
    assert user.status_code == 200
    assert user.json()["role"] == "operator"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert any(b["branch_name"] == "Filial Norte" for b in me.json()["branches"])


def test_operator_can_view_inventory_but_cannot_admin_or_edit_inventory(client):
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "op_a",
            "name": "Operador A",
            "password": "senhaop",
            "role": "operator",
        },
    )
    assert r.status_code == 200
    op = _login("op_a", "senhaop", "test-a")

    assert op.get("/api/v1/inventory").status_code == 200
    assert op.get("/api/v1/admin/locadora").status_code == 403
    edit = op.put(
        "/api/v1/inventory/items/ESC-OP",
        json={"section": "telescopic_shores", "qty": 1},
    )
    assert edit.status_code == 403


def test_viewer_is_read_only_for_jobs(client):
    r = client.post(
        "/api/v1/admin/users",
        json={
            "username": "viewer_a",
            "name": "Viewer A",
            "password": "senhaview",
            "role": "viewer",
        },
    )
    assert r.status_code == 200
    viewer = _login("viewer_a", "senhaview", "test-a")

    assert viewer.get("/api/v1/jobs").status_code == 200
    assert viewer.get("/api/v1/inventory").status_code == 403
    assert viewer.get("/api/v1/inventory/template.xlsx").status_code == 403
    upload = viewer.post(
        "/api/v1/jobs",
        files={"file": ("planta.dxf", "0\nEOF\n", "application/dxf")},
    )
    assert upload.status_code == 403
    assert viewer.delete("/api/v1/jobs/qualquer").status_code == 403
