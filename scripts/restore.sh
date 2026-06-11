#!/usr/bin/env bash
#
# restore.sh — восстановление SkillShare Network «из нуля» после аварии:
#   1) накат структуры и данных из дампа PostgreSQL (.sql);
#   2) распаковка архива медиа-файлов обратно в рабочий каталог приложения.
#
# Доступы берутся из .env (SSN_DATABASE_URL) — паролей в коде нет.
#
# Использование:
#   ./scripts/restore.sh                         # последний бэкап из backups/data
#   ./scripts/restore.sh path/to/db_backup.sql   # конкретный дамп (+ парный media-архив)
#   FORCE=1 ./scripts/restore.sh                  # без интерактивного подтверждения
#   DB_CONTAINER=db ./scripts/restore.sh          # через docker compose exec
#
# shellcheck source=scripts/_env.sh

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_env.sh"

load_env
parse_database_url

# 1. Выбираем дамп БД: аргумент №1 или самый свежий в каталоге бэкапов.
DB_DUMP="${1:-}"
if [[ -z "$DB_DUMP" ]]; then
  DB_DUMP="$(ls -1t "$BACKUP_DIR"/db_backup_*.sql 2>/dev/null | head -n1 || true)"
fi
[[ -n "$DB_DUMP" && -f "$DB_DUMP" ]] || die "дамп БД не найден: '${DB_DUMP:-<нет файлов в $BACKUP_DIR>}'"

# 2. Парный медиа-архив определяем по таймстампу из имени дампа.
STAMP="$(basename "$DB_DUMP" | sed -E 's/^db_backup_(.*)\.sql$/\1/')"
MEDIA_ARCHIVE="${2:-$BACKUP_DIR/media_backup_${STAMP}.tar.gz}"

echo "ВНИМАНИЕ: база '$PGDATABASE' на $PGHOST:$PGPORT будет перезаписана!"
echo "  Дамп БД : $DB_DUMP"
echo "  Медиа   : $MEDIA_ARCHIVE"
if [[ "${FORCE:-0}" != "1" ]]; then
  read -rp "Продолжить восстановление? [y/N] " answer
  [[ "$answer" == [yY] ]] || die "отменено пользователем"
fi

echo "==> [1/2] Восстановление БД из $DB_DUMP"
# Дамп создан с --clean --if-exists: существующие объекты дропаются перед накатом.
run_psql -d "$PGDATABASE" -v ON_ERROR_STOP=1 < "$DB_DUMP"

echo "==> [2/2] Восстановление медиа из $MEDIA_ARCHIVE"
if [[ -f "$MEDIA_ARCHIVE" ]]; then
  mkdir -p "$MEDIA_DIR"
  rm -rf "${MEDIA_DIR:?}"/*           # :? страхует от случайного rm -rf /
  tar -xzf "$MEDIA_ARCHIVE" -C "$(dirname "$MEDIA_DIR")"
else
  echo "    ВНИМАНИЕ: медиа-архив '$MEDIA_ARCHIVE' не найден — шаг пропущен"
fi

echo "==> Готово. Система восстановлена, перезапустите приложение."
