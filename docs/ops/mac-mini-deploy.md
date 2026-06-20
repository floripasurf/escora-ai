# Runbook — engine do estrutura.app no Mac Mini

Topologia atual (pós-cutover do Fly, PR #2):

- **Web**: estático no Vercel (`web/`), projeto `escora-ai`.
- **Engine**: FastAPI (`uvicorn api.main:app`) no **Mac Mini**, exposto por
  **Cloudflare Tunnel** em `https://escora.blackcube.dev`.
- O frontend chama o tunnel direto (`web/index.html` → `BACKEND`), evitando o
  limite de ~4.5 MB do edge da Vercel em uploads grandes.

> O `fly-deploy.yml` foi desativado (movido para `Quarantine/`): o Fly não é
> mais o alvo de produção. Deploy do engine é manual no Mac Mini (abaixo).

## 1. Variável crítica: `ESCORA_DATA_DIR`

Todo o estado durável (jobs.db, sessions.db, registry.db, `inventory/`,
`learning/`, `uploads/`, `output/`) vive sob `ESCORA_DATA_DIR`. O default é
`./data` **relativo ao CWD** — se o serviço subir de outro diretório sem a
variável, ele cria um `./data` vazio e re-seeda do `data/locadoras.json`,
"perdendo" tenants/jobs reais.

**Sempre** aponte para um caminho absoluto estável, ex:
`/Users/SEU_USER/estrutura-data`. O launchd unit abaixo fixa isso.

## 2. Auto-restart (launchd) — resolve o SPOF "processo sem supervisor"

```bash
cp scripts/ops/com.estrutura.engine.plist ~/Library/LaunchAgents/
# edite e troque __REPO_DIR__ / __VENV_BIN__ / __DATA_DIR__ pelos caminhos reais
mkdir -p "$ESCORA_DATA_DIR/logs"
launchctl load -w ~/Library/LaunchAgents/com.estrutura.engine.plist
launchctl list | grep estrutura
```

`KeepAlive=true` reinicia o uvicorn se ele cair (crash/OOM); `RunAtLoad=true`
sobe no boot do Mac Mini.

## 3. Backups — resolve "perda de disco = perda total"

Agende o backup diário (launchd ou `cron`):

```bash
ESCORA_DATA_DIR=/Users/SEU_USER/estrutura-data \
BACKUP_DEST=/Users/SEU_USER/estrutura-backups \
bash scripts/ops/backup_data.sh
```

Faz `.backup` consistente dos SQLite (seguro com WAL) + tar de
`inventory/ learning/ uploads/ output/`, mantendo os últimos 14. Idealmente
sincronize `BACKUP_DEST` para fora da máquina (rsync/iCloud/S3).

## 4. Deploy de nova versão

```bash
cd __REPO_DIR__ && git pull
__VENV_BIN__/pip install -r requirements.txt   # se mudou deps
launchctl kickstart -k gui/$(id -u)/com.estrutura.engine   # reinicia o engine
curl -s https://escora.blackcube.dev/api/v1/health         # smoke
```

## 5. Checklist antes de convidar parceiros

- [ ] `ESCORA_DATA_DIR` absoluto e setado no launchd unit
- [ ] launchd unit carregado (`launchctl list | grep estrutura`)
- [ ] backup diário agendado e testado (restauração validada uma vez)
- [ ] `cloudflared` rodando como serviço (auto-restart próprio) e tunnel ativo
- [ ] health responde via `https://escora.blackcube.dev/api/v1/health`
- [ ] CORS allowlist + rate-limit no login aplicados (PR #1 — ver P0-3/P0-4)
