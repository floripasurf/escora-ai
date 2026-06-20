"""Controlled pilot provisioning script tests."""

import json
import os
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_provision_pilot_locadoras_creates_registry_and_inventories(tmp_path):
    data_dir = tmp_path / "data"
    locadoras_file = tmp_path / "locadoras.json"
    locadoras_file.write_text(json.dumps({"version": 1, "locadoras": []}), encoding="utf-8")

    complete = _write_json(
        tmp_path / "complete.json",
        {
            "telescopic_shores": {"ESC310": 10},
            "tower_modules": {"TWR-TA100": 5},
            "distribution_beams": {"VD-VM130-410": 3},
        },
    )
    partial = _write_json(
        tmp_path / "partial.json",
        {
            "telescopic_shores": {"ESC310": 2},
            "tower_modules": {},
            "distribution_beams": {},
        },
    )
    custom = _write_json(
        tmp_path / "custom.json",
        {
            "telescopic_shores": {
                "ESC-PROPRIA": {
                    "qty": 4,
                    "capacity_kn": 22,
                    "height_min_m": 2.0,
                    "height_max_m": 5.0,
                }
            },
            "tower_modules": {},
            "distribution_beams": {},
        },
    )

    env = {
        **os.environ,
        "ESCORA_LOCADORAS_FILE": str(locadoras_file),
        "PYTHONPATH": str(Path.cwd()),
    }
    result = subprocess.run(
        [
            sys.executable,
            "scripts/provision_pilot_locadoras.py",
            "--data-dir",
            str(data_dir),
            "--owner-password",
            "senha123",
            "--complete",
            str(complete),
            "--partial",
            str(partial),
            "--custom",
            str(custom),
        ],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert len(summary["pilots"]) == 3
    assert (data_dir / "registry.db").exists()
    assert (data_dir / "inventory" / "pilot-complete.json").exists()
    assert (data_dir / "inventory" / "pilot-partial.json").exists()
    custom_payload = json.loads((data_dir / "inventory" / "pilot-custom.json").read_text())
    assert custom_payload["telescopic_shores"]["ESC-PROPRIA"]["capacity_kn"] == 22

    # Idempotent rerun: existing pilot owners are reused and inventories rewritten.
    rerun = subprocess.run(
        result.args,
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert rerun.returncode == 0, rerun.stderr
