"""Test fixtures: seed a temporary locadoras registry and an authenticated client.

We seed two independent locadoras (A and B) each with one branch and one user,
so cross-tenant isolation can be verified without crossing the Locadora line.
"""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient


def _hash(password: str, salt: str = "testsalt") -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"pbkdf2:sha256:100000${salt}${dk.hex()}"


SEED_LOCADORAS = {
    "version": 1,
    "updated_at": "2026-04-07",
    "locadoras": [
        {
            "id": "loc-a",
            "name": "Locadora A",
            "metodologia": {"laje_layout": "line_first"},
            "branches": [
                {
                    "id": "test-a",
                    "branch_name": "Unit A",
                    "inventory_name": "orguel_sjc",
                }
            ],
            "users": [
                {
                    "username": "eng_a",
                    "name": "Engenheiro A",
                    "password_hash": _hash("senhaA"),
                }
            ],
        },
        {
            "id": "loc-b",
            "name": "Locadora B",
            "branches": [
                {
                    "id": "test-b",
                    "branch_name": "Unit B",
                    "inventory_name": "loc_b_unit",
                }
            ],
            "users": [
                {
                    "username": "eng_b",
                    "name": "Engenheiro B",
                    "password_hash": _hash("senhaB"),
                }
            ],
        },
    ],
}


@pytest.fixture(autouse=True)
def _isolated_data(tmp_path_factory, monkeypatch):
    """Isolate every test in its own data dir so jobs.db, sessions.db,
    learning/ and uploads/ can't leak between tests."""
    data_dir = tmp_path_factory.mktemp("data")
    loc_file = data_dir / "locadoras.json"
    loc_file.write_text(json.dumps(SEED_LOCADORAS))

    monkeypatch.setenv("ESCORA_DATA_DIR", str(data_dir))
    monkeypatch.setenv("ESCORA_LOCADORAS_FILE", str(loc_file))
    # Every test shares the TestClient "IP"; the limiter is tested explicitly
    # in test_ratelimit.py, which unsets this.
    monkeypatch.setenv("ESCORA_RATE_LIMIT_DISABLED", "1")

    from src.auth.branches import clear_sessions
    from api.services.job_service import _reset_for_tests
    from api import ratelimit
    clear_sessions()
    _reset_for_tests()
    ratelimit.reset()
    yield
    clear_sessions()


def _login(tc: TestClient, username: str, password: str, branch_id: str) -> TestClient:
    r = tc.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    tc.headers.update({
        "Authorization": f"Bearer {token}",
        "X-Branch-Id": branch_id,
    })
    return tc


@pytest.fixture
def client():
    from api.main import app
    c = TestClient(app)
    return _login(c, "eng_a", "senhaA", "test-a")


@pytest.fixture
def client_b():
    from api.main import app
    c = TestClient(app)
    return _login(c, "eng_b", "senhaB", "test-b")


@pytest.fixture
def client_unauth():
    from api.main import app
    return TestClient(app)
