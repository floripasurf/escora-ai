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


def test_owner_can_rename_and_delete_extra_branch(client):
    branch = client.post(
        "/api/v1/admin/branches",
        json={"branch_name": "Filial Sul", "inventory_name": "filial_sul"},
    )
    assert branch.status_code == 200
    branch_id = branch.json()["id"]

    renamed = client.patch(
        f"/api/v1/admin/branches/{branch_id}",
        json={"branch_name": "Filial Sul Renomeada"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["branch_name"] == "Filial Sul Renomeada"
    me = client.get("/api/v1/auth/me")
    assert any(b["branch_name"] == "Filial Sul Renomeada" for b in me.json()["branches"])

    deleted = client.delete(f"/api/v1/admin/branches/{branch_id}")
    assert deleted.status_code == 200
    me = client.get("/api/v1/auth/me")
    assert all(b["id"] != branch_id for b in me.json()["branches"])


def test_owner_cannot_delete_last_branch(client):
    r = client.delete("/api/v1/admin/branches/test-a")
    assert r.status_code == 400
    assert "ultima unidade" in r.json()["detail"]


def test_owner_can_delete_user_but_not_self_or_last_owner(client):
    created = client.post(
        "/api/v1/admin/users",
        json={
            "username": "temp_user",
            "name": "Usuario Temporario",
            "password": "senha123",
            "role": "viewer",
        },
    )
    assert created.status_code == 200
    deleted = client.delete("/api/v1/admin/users/temp_user")
    assert deleted.status_code == 200

    self_delete = client.delete("/api/v1/admin/users/eng_a")
    assert self_delete.status_code == 400
    assert "proprio usuario" in self_delete.json()["detail"]

    admin_user = client.post(
        "/api/v1/admin/users",
        json={
            "username": "admin_a",
            "name": "Admin A",
            "password": "senha123",
            "role": "admin",
        },
    )
    assert admin_user.status_code == 200
    admin = _login("admin_a", "senha123", "test-a")
    last_owner = admin.delete("/api/v1/admin/users/eng_a")
    assert last_owner.status_code == 400
    assert "ultimo owner" in last_owner.json()["detail"]

    second_owner = client.post(
        "/api/v1/admin/users",
        json={
            "username": "owner2",
            "name": "Owner Dois",
            "password": "senha123",
            "role": "owner",
        },
    )
    assert second_owner.status_code == 200
    assert client.delete("/api/v1/admin/users/owner2").status_code == 200


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
