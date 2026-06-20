"""Self-service inventory API tests."""

from concurrent.futures import ThreadPoolExecutor
import csv
import json
import os
from pathlib import Path
import zipfile
import io

from src.engine.inventory import load_inventory, update_inventory
from api.services.inventory_service import template_xlsx


def _inventory_file(name: str) -> Path:
    path = Path(os.environ["ESCORA_DATA_DIR"]) / "inventory" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_get_inventory_returns_current_branch_file(client):
    _inventory_file("orguel_sjc").write_text(
        json.dumps(
            {
                "tenant_id": "orguel_sjc",
                "locadora": "Teste A",
                "updated_at": "2026-06-19",
                "telescopic_shores": {
                    "ESC999": {
                        "qty": 12,
                        "capacity_kn": 20,
                        "height_min_m": 2.0,
                        "height_max_m": 5.2,
                    }
                },
                "tower_modules": {},
                "distribution_beams": {},
            }
        ),
        encoding="utf-8",
    )

    r = client.get("/api/v1/inventory")
    assert r.status_code == 200
    data = r.json()
    assert data["inventory_name"] == "orguel_sjc"
    item = data["items"][0]
    assert item["model_id"] == "ESC999"
    assert item["qty"] == 12
    assert item["height_max_m"] == 5.2


def test_put_inventory_item_persists_for_engine_loader(client):
    r = client.put(
        "/api/v1/inventory/items/ESC500",
        json={
            "section": "telescopic_shores",
            "qty": 7,
            "capacity_kn": 18.5,
            "height_min_m": 2.1,
            "height_max_m": 5.0,
            "notes": "Escora estendida",
        },
    )

    assert r.status_code == 200
    item = next(i for i in r.json()["items"] if i["model_id"] == "ESC500")
    assert item["qty"] == 7
    assert item["capacity_kn"] == 18.5

    inv = load_inventory("orguel_sjc")
    assert inv.items["ESC500"] == 7
    assert inv.specs["ESC500"].height_max_m == 5.0


def test_delete_inventory_item(client):
    client.put(
        "/api/v1/inventory/items/VD-VM80",
        json={"section": "distribution_beams", "qty": 3},
    )
    r = client.delete("/api/v1/inventory/items/VD-VM80")
    assert r.status_code == 200
    assert all(i["model_id"] != "VD-VM80" for i in r.json()["items"])

    assert client.delete("/api/v1/inventory/items/VD-VM80").status_code == 404


def test_put_inventory_replaces_full_table(client):
    r = client.put(
        "/api/v1/inventory",
        json={
            "locadora": "Tabela completa",
            "telescopic_shores": {"ESC100": {"qty": 10, "capacity_kn": 12}},
            "tower_modules": {},
            "distribution_beams": {"VD-VM50": 4},
        },
    )
    assert r.status_code == 200
    models = {i["model_id"]: i for i in r.json()["items"]}
    assert set(models) == {"ESC100", "VD-VM50"}
    assert models["VD-VM50"]["qty"] == 4


def test_put_inventory_rejects_invalid_full_table(client):
    r = client.put(
        "/api/v1/inventory",
        json={
            "telescopic_shores": {"ESC-BAD": {"qty": -1}},
            "tower_modules": {},
            "distribution_beams": {},
        },
    )
    assert r.status_code == 400
    assert "Quantidade" in r.json()["detail"]


def test_atomic_inventory_updates_preserve_concurrent_mutations():
    def add_model(model_id: str):
        def mutate(data):
            data.setdefault("locadora", "Concurrent")
            data.setdefault("telescopic_shores", {})
            data["telescopic_shores"][model_id] = {"qty": 1}
            return data

        update_inventory("concurrent_unit", mutate)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(add_model, ["ESC-A", "ESC-B"]))

    inv = load_inventory("concurrent_unit")
    assert inv.items["ESC-A"] == 1
    assert inv.items["ESC-B"] == 1


def test_import_csv_replaces_only_selected_branch_inventory(client, client_b):
    csv_text = (
        "Modelo,Tipo,Quantidade,Capacidade (kN),Altura minima (m),Altura maxima (m)\n"
        "ESC310,Escora metalica,100,15,1.8,3.1\n"
        "TWR-TA100,Torre de escoramento,5,100,,\n"
    )

    r = client.post(
        "/api/v1/inventory/import-csv",
        files={"file": ("inventario.csv", csv_text, "text/csv")},
    )
    assert r.status_code == 200
    assert {i["model_id"] for i in r.json()["items"]} == {"ESC310", "TWR-TA100"}

    other = client_b.get("/api/v1/inventory")
    assert other.status_code == 200
    assert all(i["model_id"] != "ESC310" for i in other.json()["items"])


def test_template_csv_lists_catalog_models_zeroed(client):
    r = client.get("/api/v1/inventory/template.csv")
    assert r.status_code == 200
    text = r.text
    rows = list(csv.DictReader(io.StringIO(text)))
    by_model = {row["Modelo"]: row for row in rows}

    assert all(value not in (None, "") for row in rows for value in row.values())
    assert "ESC2000-3100,Escora metalica,0" in text
    assert "ESC310,Escora metalica,0" in text
    assert "TWR-TA150,Torre de escoramento,0" in text
    assert "VD-VM50-410,Viga de distribuicao,0" in text
    assert "VD-VM80-155,Barrote / viga de distribuicao,0" in text
    assert "CRZ-TORRE,Acessorio,0" in text
    assert by_model["TWR-TA100"]["Capacidade (kN)"] == "39.3"
    assert by_model["TWR-TA100"]["Altura minima (m)"] == "1.0"
    assert by_model["TWR-TA100"]["Curva"] == "1:39.3;5:34.8;10:32.8;15:30.8;20:28.9"
    assert by_model["TWR-TA150"]["Capacidade (kN)"] == "78.5"
    assert by_model["TWR-TA150"]["Altura minima (m)"] == "1.5"
    assert by_model["TWR-TA150"]["Curva"] == "1.5:78.5;7.5:69.5;15:65.5;22.5:61.6;30:57.7"
    assert by_model["VD-VM130-155"]["Momento adm (kN.m)"] == "5.06"
    assert by_model["VD-VM130-155"]["Vao max (m)"] == "1.55"
    assert not by_model["VD-VM130-155"]["Observacoes"].startswith("M_adm=")


def test_template_xlsx_download_is_valid_workbook(client):
    r = client.get("/api/v1/inventory/template.xlsx")
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = set(zf.namelist())
        assert "xl/workbook.xml" in names
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "ESC2000-3100" in sheet
        assert "VD-VM50-410" in sheet


def test_import_xlsx_template(client):
    content = template_xlsx()
    r = client.post(
        "/api/v1/inventory/import-csv",
        files={
            "file": (
                "inventario.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200
    models = {i["model_id"]: i for i in r.json()["items"]}
    assert models["ESC2000-3100"]["qty"] == 0
    assert models["VD-VM80-155"]["section"] == "distribution_beams"
    assert models["CRZ-TORRE"]["section"] == "accessories"


def test_inventory_requires_branch_context(client_unauth):
    r = client_unauth.get("/api/v1/inventory")
    assert r.status_code == 401
