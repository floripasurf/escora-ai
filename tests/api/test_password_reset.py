"""Sprint 5: fluxo de redefinição de senha (token single-use, TTL 1h)."""


def test_request_reset_always_200(client_unauth):
    r = client_unauth.post(
        "/api/v1/auth/request-reset", json={"email": "naoexiste@x.com"}
    )
    assert r.status_code == 200
    r2 = client_unauth.post(
        "/api/v1/auth/request-reset", json={"email": "eng_a"}
    )
    assert r2.status_code == 200
    # Mesma mensagem nos dois casos — não vaza existência da conta.
    assert r.json() == r2.json()


def test_full_reset_flow(client_unauth):
    from src.auth.branches import create_reset_token

    token = create_reset_token("eng_a")

    r = client_unauth.post(
        "/api/v1/auth/reset",
        json={"token": token, "new_password": "novaSenha123"},
    )
    assert r.status_code == 200

    # Senha antiga não funciona mais; nova funciona.
    old = client_unauth.post(
        "/api/v1/auth/login", json={"username": "eng_a", "password": "senhaA"}
    )
    assert old.status_code == 401
    new = client_unauth.post(
        "/api/v1/auth/login",
        json={"username": "eng_a", "password": "novaSenha123"},
    )
    assert new.status_code == 200


def test_token_is_single_use(client_unauth):
    from src.auth.branches import create_reset_token

    token = create_reset_token("eng_a")
    first = client_unauth.post(
        "/api/v1/auth/reset", json={"token": token, "new_password": "senha123"}
    )
    assert first.status_code == 200
    second = client_unauth.post(
        "/api/v1/auth/reset", json={"token": token, "new_password": "outra123"}
    )
    assert second.status_code == 400


def test_reset_revokes_existing_sessions(client, client_unauth):
    """Sessão ativa do usuário morre após o reset (token de conta roubada)."""
    from src.auth.branches import create_reset_token

    assert client.get("/api/v1/jobs").status_code == 200
    token = create_reset_token("eng_a")
    client_unauth.post(
        "/api/v1/auth/reset", json={"token": token, "new_password": "senha123"}
    )
    assert client.get("/api/v1/jobs").status_code == 401


def test_expired_token_rejected(client_unauth, monkeypatch):
    from src.auth import branches

    token = branches.create_reset_token("eng_a")
    real_time = branches.time.time
    monkeypatch.setattr(
        branches.time, "time",
        lambda: real_time() + branches.RESET_TOKEN_TTL_SECONDS + 1,
    )
    r = client_unauth.post(
        "/api/v1/auth/reset", json={"token": token, "new_password": "senha123"}
    )
    assert r.status_code == 400


def test_short_password_rejected(client_unauth):
    from src.auth.branches import create_reset_token

    token = create_reset_token("eng_a")
    r = client_unauth.post(
        "/api/v1/auth/reset", json={"token": token, "new_password": "abc"}
    )
    assert r.status_code == 400
