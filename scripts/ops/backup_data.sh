#!/usr/bin/env bash
#
# Backup do estado durável do estrutura.app (engine no Mac Mini).
#
# Faz backup consistente dos SQLite (jobs/sessions/registry) via `.backup`
# (seguro com WAL ativo) + tar dos diretórios JSON (inventário, learning,
# uploads, output). Mantém os últimos N backups.
#
# Uso (cron/launchd diário):
#   ESCORA_DATA_DIR=/Users/SEU_USER/estrutura-data \
#   BACKUP_DEST=/Users/SEU_USER/estrutura-backups \
#   bash scripts/ops/backup_data.sh
#
# Restauração: descompacte o tar do dia e/ou copie os .db de volta para
# ESCORA_DATA_DIR com o serviço PARADO.
set -euo pipefail

DATA_DIR="${ESCORA_DATA_DIR:-./data}"
DEST="${BACKUP_DEST:-./backups}"
KEEP="${BACKUP_KEEP:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${DEST}/${STAMP}"

if [ ! -d "$DATA_DIR" ]; then
  echo "ERRO: ESCORA_DATA_DIR não encontrado: $DATA_DIR" >&2
  exit 1
fi

mkdir -p "$OUT"

# SQLite: usa .backup (consistente mesmo com WAL/escritas concorrentes).
for db in jobs sessions registry; do
  src="${DATA_DIR}/${db}.db"
  if [ -f "$src" ]; then
    sqlite3 "$src" ".backup '${OUT}/${db}.db'"
    echo "ok: ${db}.db"
  fi
done

# JSON/arquivos: tar dos diretórios que não são SQLite.
tar -czf "${OUT}/files.tar.gz" -C "$DATA_DIR" \
  $( cd "$DATA_DIR" && ls -d inventory learning uploads output locadoras.json 2>/dev/null ) \
  2>/dev/null || true
echo "ok: files.tar.gz"

# Retenção: mantém apenas os últimos KEEP diretórios de backup.
ls -1dt "${DEST}"/*/ 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -I{} rm -rf "{}" || true

echo "Backup concluído em ${OUT}"
