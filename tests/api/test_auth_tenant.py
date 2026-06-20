"""Auth + tenant-isolation tests (login/password + branch selection).

Verifies that:
- endpoints refuse callers without a valid session token
- wrong username/password is rejected
- /auth/me returns locadora + branches for the session
- jobs created by branch A are invisible to branch B (different locadora)
- cross-tenant status/delete return 404
"""

import ezdxf


def _minimal_dxf(tmp_path):
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "tiny.dxf"
    doc.saveas(str(path))
    return path


# ---------- login / auth ----------

def test_login_success_returns_token_and_branches(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "eng_a", "password": "senhaA"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["token"]
    assert data["username"] == "eng_a"
    assert data["locadora_id"] == "loc-a"
    assert any(b["id"] == "test-a" for b in data["branches"])


def test_login_bad_password_rejected(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "eng_a", "password": "wrong"},
    )
    assert r.status_code == 401


def test_login_unknown_user_rejected(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "ghost", "password": "x"},
    )
    assert r.status_code == 401


def test_missing_session_rejected(client_unauth):
    r = client_unauth.get("/api/v1/jobs")
    assert r.status_code == 401


def test_unknown_token_rejected(client_unauth):
    r = client_unauth.get(
        "/api/v1/jobs",
        headers={"Authorization": "Bearer not-a-real-token", "X-Branch-Id": "test-a"},
    )
    assert r.status_code == 401


def test_missing_branch_header_rejected(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "eng_a", "password": "senhaA"},
    )
    token = r.json()["token"]
    r = client_unauth.get(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_branch_from_other_locadora_forbidden(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "eng_a", "password": "senhaA"},
    )
    token = r.json()["token"]
    r = client_unauth.get(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {token}", "X-Branch-Id": "test-b"},
    )
    assert r.status_code == 403


def test_me_returns_locadora_and_branches(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "eng_a"
    assert data["locadora_id"] == "loc-a"
    assert data["selected_branch"]["id"] == "test-a"
    assert data["selected_branch"]["inventory_name"] == "orguel_sjc"


def test_signup_accepts_first_branch_and_inventory_name(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/signup",
        json={
            "name": "Owner Piloto",
            "email": "owner.piloto@example.com",
            "company": "Locadora Piloto",
            "phone": "",
            "password": "senha123",
            "branch_name": "Curitiba",
            "inventory_name": "piloto_curitiba",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["role"] == "owner"
    assert data["locadora_name"] == "Locadora Piloto"
    assert data["branches"][0]["branch_name"] == "Curitiba"
    assert data["branches"][0]["inventory_name"] == "piloto_curitiba"


def test_signup_rejects_duplicate_inventory_name(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/signup",
        json={
            "name": "Owner Conflito",
            "email": "owner.conflito@example.com",
            "company": "Locadora Conflito",
            "password": "senha123",
            "branch_name": "Sede",
            "inventory_name": "orguel_sjc",
        },
    )
    assert r.status_code == 400
    assert "inventario" in r.json()["detail"].lower()


# ---------- methodology contract (Fase 2) ----------

def _assert_line_first_profile(m):
    """loc-a is seeded line_first → herda passo 0.60 + cobertura torre_first."""
    assert m is not None, "branch payload deve trazer 'metodologia'"
    assert m["laje_layout"] == "line_first"
    assert m["passo_sob_viga_m"] == 0.60
    assert m["cobertura"] == "torre_first"
    assert m["labels"]["laje_layout"]["pt"] == "Line-first Orguel"
    # barrote agora EXPLICITO (Fase 5): escopo cliente, nao inferido
    assert m["barrote_resumo"]["usa_barrote"] is False
    assert m["barrote_resumo"]["inferido"] is False
    assert m["barrote_resumo"]["escopo"] == "cliente"
    assert m["barrotes_escopo"] == "cliente"


def test_login_returns_methodology_per_branch(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "eng_a", "password": "senhaA"},
    )
    assert r.status_code == 200
    branch = next(b for b in r.json()["branches"] if b["id"] == "test-a")
    _assert_line_first_profile(branch["metodologia"])


def test_me_returns_methodology_for_branches_and_selected(client):
    data = client.get("/api/v1/auth/me").json()
    _assert_line_first_profile(data["selected_branch"]["metodologia"])
    branch = next(b for b in data["branches"] if b["id"] == "test-a")
    _assert_line_first_profile(branch["metodologia"])


def test_methodology_defaults_to_grid_when_unset(client_unauth):
    """loc-b nao define metodologia → perfil grid legado (com barrote)."""
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "eng_b", "password": "senhaB"},
    )
    assert r.status_code == 200
    branch = next(b for b in r.json()["branches"] if b["id"] == "test-b")
    m = branch["metodologia"]
    assert m["laje_layout"] == "grid_vm_duplo"
    assert m["barrote_resumo"]["usa_barrote"] is True


def test_logout_revokes_session(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "eng_a", "password": "senhaA"},
    )
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}", "X-Branch-Id": "test-a"}
    assert client_unauth.get("/api/v1/jobs", headers=headers).status_code == 200

    client_unauth.post("/api/v1/auth/logout", headers=headers)
    assert client_unauth.get("/api/v1/jobs", headers=headers).status_code == 401


# ---------- tenant isolation ----------

def test_list_is_scoped_to_caller_branch(client, client_b, tmp_path):
    path = _minimal_dxf(tmp_path)
    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/jobs",
            files={"file": ("tiny.dxf", f, "application/octet-stream")},
        )
    assert r.status_code == 201

    list_a = client.get("/api/v1/jobs").json()
    assert len(list_a) == 1

    list_b = client_b.get("/api/v1/jobs").json()
    assert list_b == []


def test_cross_tenant_status_returns_404(client, client_b, tmp_path):
    path = _minimal_dxf(tmp_path)
    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/jobs",
            files={"file": ("tiny.dxf", f, "application/octet-stream")},
        )
    job_id = r.json()["id"]

    assert client.get(f"/api/v1/jobs/{job_id}/status").status_code == 200
    assert client_b.get(f"/api/v1/jobs/{job_id}/status").status_code == 404


def test_cross_tenant_delete_returns_404(client, client_b, tmp_path):
    path = _minimal_dxf(tmp_path)
    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/jobs",
            files={"file": ("tiny.dxf", f, "application/octet-stream")},
        )
    job_id = r.json()["id"]

    assert client_b.delete(f"/api/v1/jobs/{job_id}").status_code == 404
    assert client.get(f"/api/v1/jobs/{job_id}/status").status_code == 200
