# Runbook — engine do estrutura.app no Mac Mini

> ⚠️ Valores abaixo refletem o setup conhecido (memória de ops); **confirme no
> Mac Mini** antes de agir — podem ter mudado.

Topologia (pós-cutover do Fly, PR #2):

- **Web**: estático no Vercel (`web/`), projeto `escora-ai` → estrutura.app.
- **Engine**: FastAPI (`uvicorn api.main:app`) no **Mac Mini** (`raphaels-mac-mini`,
  Tailscale `100.77.76.64`), em `~/escora-ai`, porta **8020**, dados em
  `~/escora-data` (`ESCORA_DATA_DIR`).
- **Exposição**: Cloudflare Tunnel `escora-ai` → `https://escora.blackcube.dev`.
  O front bate direto nesse host (fura o rewrite da Vercel pelo cap de 4.5 MB).
- **Fly.io**: app `escora-ai` PARADO (rollback). `fly-deploy.yml` foi desativado
  (movido p/ `Quarantine/`) — não há mais deploy automático.

## Já existente em produção (NÃO recriar — só verificar)

- **launchd** mantém o engine e o túnel vivos (auto-restart no boot/crash):
  `com.escora.engine` e `com.escora.tunnel`.
  ```bash
  launchctl list | grep escora
  ```
- `ESCORA_DATA_DIR=~/escora-data` já configurado no unit.

> O template `scripts/ops/com.escora.engine.plist` é só **referência** do unit
> existente — use para conferir/recriar em caso de perda, ajustando os caminhos.

## Deploy de nova versão (após merge do PR para `main`)

```bash
ssh raphaels-mac-mini   # ou via Tailscale 100.77.76.64
cd ~/escora-ai && git pull
./.venv/bin/pip install -r requirements.txt        # se mudou deps
launchctl kickstart -k gui/$(id -u)/com.escora.engine   # reinicia o uvicorn
curl -s https://escora.blackcube.dev/api/v1/health      # smoke
```

> O uvicorn segura código/estado em memória — **só reinicia via launchd**
> (`kickstart`), não basta `git pull` (incidente 2026-06-11).

## Gap real a fechar: BACKUPS (não existem hoje)

`data/*.db` (jobs/sessions/registry) + `inventory/ learning/ uploads/ output/`
vivem só no disco do Mac Mini. Agendar o backup diário:

```bash
ESCORA_DATA_DIR=~/escora-data \
BACKUP_DEST=~/escora-backups \
bash scripts/ops/backup_data.sh
```

Faz `.backup` consistente dos SQLite (WAL-safe) + tar dos diretórios JSON,
retenção 14. Sincronize `~/escora-backups` para fora da máquina (rsync/iCloud).

## Checklist antes de convidar parceiros

- [ ] BACKUP diário agendado e restauração testada uma vez (gap aberto)
- [ ] `git pull` em `~/escora-ai` + `kickstart com.escora.engine` + smoke no /health
- [ ] `SIGNUP_INVITE_CODES` setado no ambiente do engine + códigos gerados p/ pilotos
- [ ] **Rotacionar** os hashes em `data/locadoras.json` (admin `devsalt2026` + conta pessoal) e **limpar** o `registry.db` de produção se contiver dados de teste
- [ ] `launchctl list | grep escora` mostra engine + tunnel ativos
- [ ] CORS allowlist + rate-limit de login (PR #1) aplicados
