"""Sprint 5: quota mensal por locadora + bloco de reescoramento no upload."""

import ezdxf
import pytest

from api.models.schemas import ReescoramentoInput
from api.services import job_service


def _tiny_dxf(tmp_path, name="tiny.dxf"):
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / name
    doc.saveas(str(path))
    return path


def _upload(client, path, extra=None):
    with open(path, "rb") as f:
        return client.post(
            "/api/v1/jobs",
            files={"file": ("tiny.dxf", f, "application/octet-stream")},
            data=extra or {},
        )


# --- Quota ---

def test_quota_blocks_after_limit(client, tmp_path, monkeypatch):
    monkeypatch.setenv("ESCORA_DEFAULT_MONTHLY_QUOTA", "1")
    path = _tiny_dxf(tmp_path)
    assert _upload(client, path).status_code == 201
    r = _upload(client, path)
    assert r.status_code == 429
    assert "Quota mensal" in r.json()["detail"]


def test_quota_zero_means_unlimited(client, tmp_path, monkeypatch):
    monkeypatch.setenv("ESCORA_DEFAULT_MONTHLY_QUOTA", "0")
    path = _tiny_dxf(tmp_path)
    assert _upload(client, path).status_code == 201
    assert _upload(client, path).status_code == 201


def test_usage_exposes_quota(client, monkeypatch):
    monkeypatch.setenv("ESCORA_DEFAULT_MONTHLY_QUOTA", "50")
    r = client.get("/api/v1/admin/usage")
    assert r.status_code == 200
    summary = r.json()["summary"]
    assert summary["quota_jobs_mes"] == 50
    assert "jobs_este_mes" in summary


# --- ReescoramentoInput (validador do schema) ---

def test_reescoramento_desforma_antecipada_exige_justificativa():
    with pytest.raises(ValueError, match="justificativa"):
        ReescoramentoInput(desforma_dias=10)
    with pytest.raises(ValueError, match="calculista"):
        ReescoramentoInput(desforma_dias=10, desforma_justificativa="aditivo acelerador")
    ok = ReescoramentoInput(
        desforma_dias=10,
        desforma_justificativa="fcj 28 MPa comprovada por ensaio",
        calculista_aprovacao="Eng. Maria Souza, CREA-RJ 67890",
    )
    assert ok.desforma_dias == 10


def test_reescoramento_default_14_dias_sem_exigencias():
    r = ReescoramentoInput(multi_pavimento=True, num_niveis_reescoramento=2)
    assert r.desforma_dias == 14


# --- Upload com o bloco ---

def test_upload_persists_reescoramento(client, tmp_path):
    path = _tiny_dxf(tmp_path)
    payload = (
        '{"multi_pavimento": true, "num_niveis_reescoramento": 2, '
        '"fcj_aos_dias_mpa": 21, "eci_mpa": 25600, "carga_final_kn_m2": 2.5, '
        '"calculista_aprovacao": "Eng. Joao Silva, CREA-SP 12345"}'
    )
    r = _upload(client, path, extra={"reescoramento_json": payload})
    assert r.status_code == 201
    job = job_service.get_job(r.json()["id"])
    stored = job["reescoramento_json"]
    assert stored["multi_pavimento"] is True
    assert stored["num_niveis_reescoramento"] == 2
    assert stored["fcj_aos_dias_mpa"] == 21
    assert stored["desforma_dias"] == 14  # default do schema


def test_upload_rejects_invalid_reescoramento(client, tmp_path):
    path = _tiny_dxf(tmp_path)
    r = _upload(
        client, path,
        extra={"reescoramento_json": '{"desforma_dias": 10}'},
    )
    assert r.status_code == 400
    assert "reescoramento" in r.json()["detail"].lower()


# --- Ponte até o engine (run_pipeline recebe ReescoramentoData) ---

def test_process_dxf_maps_payload_to_engine(monkeypatch, tmp_path):
    from api.services import pipeline_service
    from src.rules.project import ReescoramentoData

    captured = {}

    def fake_runner(input_path, **kwargs):
        captured.update(kwargs)
        class R:
            calculation = None
            warnings = []
        return R()

    monkeypatch.setattr(pipeline_service, "run_pipeline", fake_runner)
    pipeline_service.process_dxf(
        str(_tiny_dxf(tmp_path)), "job123",
        reescoramento={
            "fcj_aos_dias_mpa": 21, "eci_mpa": 25600,
            "carga_final_kn_m2": 2.5, "num_niveis_reescoramento": 2,
            "calculista_aprovacao": "Eng. Joao Silva, CREA-SP 12345",
            "desforma_dias": 14, "desforma_justificativa": "",
        },
    )
    data = captured["reescoramento"]
    assert isinstance(data, ReescoramentoData)
    assert data.is_complete()
    assert data.num_niveis_reescoramento == 2
    assert captured["desforma_dias"] == 14
