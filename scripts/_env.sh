# shellcheck shell=bash
# Общие функции для backup.sh / restore.sh.
# Подтягивает доступы к БД из .env (никаких паролей в коде) и выбирает,
# как запускать утилиты PostgreSQL: локально или внутри docker-контейнера.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Пути можно переопределить переменными окружения (удобно для CI / Docker).
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups/data}"
MEDIA_DIR="${MEDIA_DIR:-$PROJECT_ROOT/backend/app/static}"

# DB_CONTAINER задан  -> утилиты вызываются через `docker compose exec` (прод/Docker).
# DB_CONTAINER пуст   -> используются локальные pg_dump/psql (PG_BIN — каталог с бинарниками).
DB_CONTAINER="${DB_CONTAINER:-}"
PG_BIN="${PG_BIN:-}"

die() {
  echo "ОШИБКА: $*" >&2
  exit 1
}

# Читаем ровно SSN_DATABASE_URL — не засоряем окружение остальными переменными.
load_env() {
  [[ -f "$ENV_FILE" ]] || die "файл окружения не найден: $ENV_FILE"
  DATABASE_URL="$(grep -E '^SSN_DATABASE_URL=' "$ENV_FILE" | tail -n1 | cut -d= -f2-)"
  [[ -n "${DATABASE_URL:-}" ]] || die "SSN_DATABASE_URL отсутствует в $ENV_FILE"
}

# Разбираем DSN вида postgresql+asyncpg://user:pass@host:port/dbname?params
# в стандартные переменные PG* (их понимают pg_dump/psql напрямую).
parse_database_url() {
  local url="${DATABASE_URL#*://}"        # отбрасываем схему
  local creds="${url%%@*}"                # user:pass
  local tail="${url#*@}"                  # host:port/db?params

  PGUSER="${creds%%:*}"
  PGPASSWORD="${creds#*:}"

  local hostport="${tail%%/*}"            # host:port
  PGHOST="${hostport%%:*}"
  PGPORT="${hostport#*:}"
  [[ "$PGPORT" == "$hostport" ]] && PGPORT=5432

  local dbpart="${tail#*/}"              # dbname?params
  PGDATABASE="${dbpart%%\?*}"

  [[ -n "$PGUSER" && -n "$PGDATABASE" ]] || die "не удалось разобрать SSN_DATABASE_URL"
  export PGUSER PGPASSWORD PGHOST PGPORT PGDATABASE
}

# Универсальный запуск утилиты PostgreSQL (pg_dump | psql) в выбранном режиме.
_run_tool() {
  local tool="$1"; shift
  if [[ -n "$DB_CONTAINER" ]]; then
    # Внутри контейнера БД доступна на localhost — host/port не нужны.
    docker compose exec -T -e PGPASSWORD="$PGPASSWORD" "$DB_CONTAINER" \
      "$tool" -U "$PGUSER" "$@"
  else
    local bin="$tool"
    [[ -n "$PG_BIN" ]] && bin="$PG_BIN/$tool"
    PGPASSWORD="$PGPASSWORD" "$bin" -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" "$@"
  fi
}

run_pg_dump() { _run_tool pg_dump "$@"; }
run_psql()    { _run_tool psql "$@"; }
