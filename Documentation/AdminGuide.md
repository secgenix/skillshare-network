# Руководство администратора — SkillShare Network

Документ для специалистов, разворачивающих и сопровождающих систему на боевом
сервере (Production). Описывает требования к окружению, конфигурацию обратного
прокси и регламент действий при типовых инцидентах.

---

## 1. Минимальные аппаратные и системные требования

| Ресурс | Минимум | Рекомендуется |
| --- | --- | --- |
| Операционная система | Ubuntu 22.04 LTS / любой Linux с Docker | Ubuntu 22.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 2 ГБ | 4 ГБ |
| Диск (ROM) | 20 ГБ SSD | 40 ГБ SSD |
| ПО | Docker Engine 24+, Docker Compose v2 | + утилиты `postgresql-client` |

Сетевые порты: наружу публикуется только `80` (HTTP, через nginx-контейнер
frontend). Backend (`8000`), PostgreSQL (`5432`) и Redis (`6379`) во внешнюю сеть
**не** выставляются — доступ к ним только внутри docker-сети.

---

## 2. Развёртывание (Production)

```bash
git clone <repo> && cd skillshare-network
git checkout maintenance

# 1. Создать файлы секретов (НЕ коммитятся в репозиторий)
mkdir -p secrets
echo "<длинный-случайный-секрет>" > secrets/secret_key.txt
echo "<надёжный-пароль-БД>"        > secrets/db_password.txt
chmod 600 secrets/*.txt

# 2. Поднять весь стек (db + redis + backend + frontend/nginx)
docker compose -f docker-compose.prod.yml up -d --build

# 3. Проверить состояние
docker compose -f docker-compose.prod.yml ps
curl -f http://localhost/api/v1/health
```

Миграции БД применяются автоматически в `backend/entrypoint.sh` при старте
контейнера. Применить вручную:

```bash
docker compose -f docker-compose.prod.yml exec backend uv run alembic upgrade head
```

---

## 3. Конфигурация веб-сервера (Reverse Proxy)

Обратный прокси (nginx) терминирует входящий трафик, отдаёт статику фронтенда и
проксирует запросы `/api/` на backend, скрывая внутренние порты. Конфиг —
`frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;

    # Статика фронтенда
    root /usr/share/nginx/html;
    index index.html;

    # Reverse proxy → backend:8000
    location /api/ {
        proxy_pass         http://backend:8000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # SPA fallback — все прочие пути отдаём index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

> Для HTTPS добавьте блок `listen 443 ssl;` с путями к сертификату/ключу
> (например, выпущенными Let's Encrypt) и редирект с `:80` на `:443`.

---

## 4. План аварийного восстановления (Disaster Recovery)

### Инцидент 4.1. Нарушение связности с СУБД (ошибка подключения к БД)

Симптомы: ответы `5xx` от API, в логах backend — `OperationalError` / `Connection
refused` при обращении к PostgreSQL.

Алгоритм действий:
1. Проверить статус контейнера БД: `docker compose -f docker-compose.prod.yml ps db`.
2. Посмотреть логи БД: `docker compose -f docker-compose.prod.yml logs --tail=100 db`.
3. Проверить готовность: `docker compose -f docker-compose.prod.yml exec db pg_isready -U postgres -d skillshare`.
4. Сверить `SSN_DATABASE_URL` (хост/порт/имя БД) и пароль из `secrets/db_password.txt`.
5. Перезапустить БД: `docker compose -f docker-compose.prod.yml restart db`, затем backend.
6. Если данные повреждены — восстановить из дампа (см. спринт 4 «Backup & Restore»)
   и повторно применить миграции `alembic upgrade head`.

### Инцидент 4.2. Критический сбой основного процесса backend

Симптомы: `/api/v1/health` не отвечает, контейнер `backend` в состоянии `Restarting`/`Exited`.

Алгоритм действий:
1. Снять логи: `docker compose -f docker-compose.prod.yml logs --tail=200 backend`.
2. Локализовать ошибку по трассировке (модуль логирования пишет INFO/ERROR — см. спринт 3).
3. Частые причины: невалидный `.env`/секрет, неприменённые миграции, изменённый порт БД.
4. Исправить конфигурацию и пересоздать контейнер:
   `docker compose -f docker-compose.prod.yml up -d --force-recreate backend`.
5. Подтвердить восстановление: `curl -f http://localhost/api/v1/health`.

### Инцидент 4.3. Переполнение диска

1. Оценить занятость: `df -h` и `docker system df`.
2. Очистить неиспользуемые образы/слои: `docker image prune -f`, при необходимости `docker system prune`.
3. Проверить рост логов и тома `pg_data`; настроить ротацию логов (спринт 3) и
   регулярные бэкапы с выгрузкой за пределы сервера.

---

## 5. Эксплуатационные команды

| Действие | Команда |
| --- | --- |
| Статус сервисов | `docker compose -f docker-compose.prod.yml ps` |
| Логи backend | `docker compose -f docker-compose.prod.yml logs -f backend` |
| Применить миграции | `... exec backend uv run alembic upgrade head` |
| Перезапуск сервиса | `docker compose -f docker-compose.prod.yml restart <service>` |
| Полная остановка | `docker compose -f docker-compose.prod.yml down` |
| Health-check | `curl -f http://localhost/api/v1/health` |
