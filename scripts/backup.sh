#!/usr/bin/env bash
#
# backup.sh — горячий бэкап SkillShare Network:
#   1) дамп базы PostgreSQL (pg_dump) с очисткой объектов при восстановлении;
#   2) архив пользовательских медиа-файлов (backend/app/static) в .tar.gz.
#
# Доступы берутся из .env (SSN_DATABASE_URL) — паролей в коде нет.
# Имена файлов содержат дату и время, поэтому бэкапы не перезатирают друг друга.
#
# Использование:
#   ./scripts/backup.sh                 # локальные pg_dump/psql из .env
#   DB_CONTAINER=db ./scripts/backup.sh # через docker compose exec
#
# shellcheck source=scripts/_env.sh

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_env.sh"

load_env
parse_database_url

TIMESTAMP="$(date +%Y_%m_%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

DB_DUMP="$BACKUP_DIR/db_backup_${TIMESTAMP}.sql"
MEDIA_ARCHIVE="$BACKUP_DIR/media_backup_${TIMESTAMP}.tar.gz"

echo "==> [1/2] Дамп базы '$PGDATABASE' ($PGHOST:$PGPORT) -> $DB_DUMP"
# --clean --if-exists: дамп сам дропнет объекты перед накатом => restore «из нуля».
# --no-owner --no-privileges: переносимость между окружениями.
run_pg_dump -d "$PGDATABASE" --clean --if-exists --no-owner --no-privileges > "$DB_DUMP"

echo "==> [2/2] Архив медиа '$MEDIA_DIR' -> $MEDIA_ARCHIVE"
if [[ -d "$MEDIA_DIR" ]]; then
  tar -czf "$MEDIA_ARCHIVE" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
else
  echo "    ВНИМАНИЕ: каталог медиа '$MEDIA_DIR' не найден — создаю пустой архив-заглушку"
  tar -czf "$MEDIA_ARCHIVE" --files-from /dev/null
fi

echo "==> Готово:"
echo "    БД    : $DB_DUMP ($(du -h "$DB_DUMP" | cut -f1))"
echo "    Медиа : $MEDIA_ARCHIVE ($(du -h "$MEDIA_ARCHIVE" | cut -f1))"
