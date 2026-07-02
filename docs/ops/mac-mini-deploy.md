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

## BACKUPS

`data/*.db` (jobs/sessions/registry) + `inventory/ learning/ uploads/ output/`
vivem só no disco do Mac Mini.

**Agendamento (launchd, diário 03:00):** unit pronto em
`scripts/ops/com.escora.backup.plist` (substituir USER pelos caminhos reais):

```bash
cp scripts/ops/com.escora.backup.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.escora.backup.plist
launchctl kickstart gui/$(id -u)/com.escora.backup   # teste imediato
tail ~/escora-backups/backup.log
```

O script faz `.backup` consistente dos SQLite (WAL-safe) + tar dos diretórios
JSON, retenção 14. Sincronize `~/escora-backups` para fora da máquina
(rsync/iCloud) — backup no mesmo disco não protege contra falha do disco.

**Procedimento de RESTORE (testar uma vez ao instalar):**

```bash
# 1. Parar o engine
launchctl bootout gui/$(id -u)/com.escora.engine
# 2. Copiar os .db do backup escolhido de volta
cp ~/escora-backups/<STAMP>/*.db ~/escora-data/
# (se necessário: descompactar o tar dos diretórios por cima de ~/escora-data)
# 3. Religar e validar
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.escora.engine.plist
curl -s http://127.0.0.1:8020/api/v1/health   # status ok + jobs_count esperado
# 4. Login em estrutura.app + histórico de jobs visível
```

## Checklist antes de convidar parceiros

- [ ] BACKUP diário agendado e restauração testada uma vez (gap aberto)
- [ ] `git pull` em `~/escora-ai` + `kickstart com.escora.engine` + smoke no /health
- [ ] `SIGNUP_INVITE_CODES` setado no ambiente do engine + códigos gerados p/ pilotos
- [ ] **Rotacionar** as senhas reais no `registry.db` de produção (admin Orguel + conta pessoal — os hashes antigos vazaram no histórico git antes do sprint-1) e **limpar** dados de teste:
  ```bash
  cd ~/escora-ai && ESCORA_DATA_DIR=~/escora-data .venv/bin/python -c "
  from src.auth.registry import update_password
  from src.auth.branches import hash_password
  update_password('admin', hash_password('NOVA_SENHA_FORTE'))"
  ```
- [ ] `launchctl list | grep escora` mostra engine + tunnel ativos
- [x] CORS allowlist + rate-limit de login aplicados (sprint-1-security). Origins extras via env `ESCORA_CORS_ORIGINS` (CSV); rate-limit usa `CF-Connecting-IP` atrás do tunnel e desliga com `ESCORA_RATE_LIMIT_DISABLED=1`

> **Nota (sprint-1):** `data/locadoras.json` saiu do repositório (segredos versionados).
> O seed inicial agora usa `data/locadoras.example.json` como template — copie para o
> caminho de `ESCORA_LOCADORAS_FILE` com hashes reais. Produção não é afetada: o
> `registry.db` existente continua sendo a fonte de verdade.
