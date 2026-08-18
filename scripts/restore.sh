#!/usr/bin/env bash
# Restaura un backup generado por backup.sh.
# Uso: ./scripts/restore.sh backups/finapp_backup_XXXXXXXX.sql.gz
set -euo pipefail

cd "$(dirname "$0")/.."
source .env

if [ $# -lt 1 ]; then
  echo "Uso: $0 <archivo_backup.sql.gz>"
  exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
  echo "Archivo no encontrado: $BACKUP_FILE"
  exit 1
fi

echo "ATENCION: esto sobrescribira la base de datos actual (${POSTGRES_DB:-finapp})."
read -p "¿Continuar? (escribe 'si' para confirmar): " CONFIRM
if [ "$CONFIRM" != "si" ]; then
  echo "Cancelado."
  exit 0
fi

gunzip -c "$BACKUP_FILE" | docker compose exec -T db psql -U "${POSTGRES_USER:-finapp}" "${POSTGRES_DB:-finapp}"
echo "Restauracion completada."
