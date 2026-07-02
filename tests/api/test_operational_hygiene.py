from pathlib import Path

from api.config import settings


def test_health_does_not_expose_local_data_dir(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "data_dir" not in response.json()


def test_frontend_upload_limit_copy_matches_backend_config():
    html = Path("web/index.html").read_text()
    expected = f"ate {settings.max_file_size_mb} MB"

    assert expected in html
    assert "ate 200 MB" not in html


def test_static_generation_pages_send_auth_headers():
    for path in ("web/projetos.html", "web/design.html"):
        html = Path(path).read_text()

        assert "escora_token" in html
        assert "escora_branch_id" in html
        assert "authHeaders" in html
        assert "X-Branch-Id" in html


def test_upload_flow_has_inline_feedback_and_size_guard():
    html = Path("web/index.html").read_text()

    assert 'id="uploadMsg"' in html
    assert "MAX_UPLOAD_MB" in html
    assert "setUploadMessage" in html
    assert "alert(msg || 'Erro no upload')" not in html


def test_inventory_tab_has_no_fake_development_alerts():
    html = Path("web/index.html").read_text()

    assert "Funcionalidade em desenvolvimento" not in html
