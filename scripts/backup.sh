#!/usr/bin/env bash
# Backup de la base de datos PostgreSQL sin exponerla a Internet.
# Se ejecuta usando el contenedor Docker existente (docker compose exec).
set -euo pipefail

cd "$(dirname "$0")/.."
source .env

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/finapp_backup_${TIMESTAMP}.sql.gz"

echo "Generando backup en $BACKUP_FILE ..."
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-finapp}" "${POSTGRES_DB:-finapp}" | gzip > "$BACKUP_FILE"

echo "Backup completado: $BACKUP_FILE"
