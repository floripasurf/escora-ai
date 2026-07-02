# Escora.AI

Backend FastAPI + frontend estatico do estrutura.app.

## Local setup

```bash
python3 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -e '.[dev]'
```

## Run

```bash
ESCORA_DATA_DIR="$PWD/data" \
ESCORA_LOCADORAS_FILE="$PWD/data/locadoras.json" \
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8020
```

## Test

```bash
.venv/bin/python -m pytest
```

Targeted security/ops regression slice:

```bash
.venv/bin/python -m pytest \
  tests/api/test_projects_security.py \
  tests/api/test_generation_auth.py \
  tests/api/test_operational_hygiene.py -q
```

## Production runtime

The active production backend for `estrutura.app` is currently the Mac Mini
process behind the Cloudflare tunnel `escora.blackcube.dev`.

Before changing production routing, run:

```bash
.venv/bin/python scripts/verify_production_runtime.py --allow-current-mac-tunnel
```

Run without `--allow-current-mac-tunnel` in CI or before a hosted-backend
migration; it fails while Vercel still points API traffic at the Mac Mini.
