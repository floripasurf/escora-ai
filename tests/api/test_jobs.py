import pytest
import ezdxf


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200


def test_upload_dxf(client, tmp_path):
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "test.dxf"
    doc.saveas(str(path))

    with open(path, "rb") as f:
        r = client.post(
            "/api/v1/jobs",
            files={"file": ("test.dxf", f, "application/octet-stream")},
        )
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert data["status"] in ("pending", "processing")


def test_get_job_status(client, tmp_path):
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (10, 0))
    path = tmp_path / "test.dxf"
    doc.saveas(str(path))

    with open(path, "rb") as f:
        r = client.post("/api/v1/jobs", files={"file": ("test.dxf", f, "application/octet-stream")})
    job_id = r.json()["id"]

    r = client.get(f"/api/v1/jobs/{job_id}/status")
    assert r.status_code == 200
    assert r.json()["status"] in ("pending", "processing", "completed", "error")
