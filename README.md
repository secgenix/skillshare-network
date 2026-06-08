## SkillShare Network

Платформа для обмена навыками, где пользователи публикуют свои предложения (что они умеют и чему могут обучить) и указывают, что хотят получить взамен. Другие пользователи могут откликаться на эти предложения, и при взаимном интересе система создаёт сделку между двумя людьми.

Каждая сделка проходит через статусы: обсуждение, активный обмен и завершение. После создания сделки автоматически открывается чат внутри неё, через который участники договариваются и ведут сам обмен. В активной сделке переписка доступна только между участниками этой сделки, и она существует только в рамках её жизненного цикла.

После завершения сделки оба пользователя подтверждают результат и оценивают друг друга, формируя рейтинг доверия.

Отдельно есть вкладка “чаты”: там отображаются все текущие и завершённые сделки. Однако писать можно только в активных сделках — завершённые чаты остаются в виде архива истории и доступны только для просмотра, без возможности продолжить переписку.

Дополнительно система использует матчмейкинг, который анализирует навыки, запросы и историю обменов, чтобы предлагать наиболее подходящих людей для потенциального обмена с высокой вероятностью совпадения интересов.

## Технологический стек

| Слой | Технология | Почему |
| --- | --- | --- |
| Backend | Python 3.12 + FastAPI | Максимальная скорость, асинхронность, мощная типизация (Pydantic) |
| Linter / Formatter | Ruff | Заменяет Flake8, Black и Isort. Молниеносная проверка кода |
| Frontend | React + Vite | Современный компонентный подход, быстрая разработка |
| UI-компоненты | TailwindCSS | Профессиональный UI с минимальными стилями |
| ORM | SQLAlchemy 2.0 + Alembic | Работа со сложным SQL и рекурсиями для матчинга цепочек |
| База данных | PostgreSQL 16+ | Реляционная классика, идеальна для графовых запросов (CTE) |
| Real-time | WebSockets | Real-time чат через `/api/v1/chat/{id}/ws` |
| Auth | JWT + X-User-Id header | MVP-аутентификация через заголовки (см. `app/api/deps.py`) |
| Ops | Docker + GitHub Actions | Стандарт индустрии для контейнеризации и автоматизации |

## Архитектурный план (следующий спринт)

Каркас бэкенда подготовлен для расширения:

| Фича | Статус | Файл |
| --- | --- | --- |
| WebSocket чат | ✅ Работает | `app/ws/manager.py`, `app/api/v1/chat.py` |
| Правила переписки | ✅ Готов | `app/policies/exchange_messaging.py` |
| Redis кэш | 🔄 Планируется | - |
| Рекурсивные CTE для графов | 🔄 Планируется | SQLAlchemy 2.0 поддерживает CTE |
| Chain matching | 🔄 Планируется | Поиск цепочек обмена A→B→C |

## Структура репозитория

Верхний уровень:

- `pyproject.toml`, `uv.lock`, `.python-version`: конфигурация uv-проекта (в корне)
- `.env`, `.env.example`: переменные окружения (в корне)
- `main.py`: точка входа для запуска из корня (реэкспортирует `app` из `backend/app`)
- `backend/`: FastAPI-приложение, DB-слой и миграции Alembic
- `frontend/`: React-приложение (Vite + TailwindCSS)
- `docker-compose.yml` / `docker-compose.prod.yml`: оркестрация dev / prod
- `Documentation/`: архитектура, руководство администратора и описание системы

Структура backend-приложения (`backend/app/`):

```text
backend/
├── alembic/              # миграции схемы БД (env.py + versions/)
├── alembic.ini           # конфиг Alembic
├── gunicorn_conf.py      # настройки прод-сервера Gunicorn/Uvicorn worker
├── entrypoint.sh         # точка входа контейнера (миграции + запуск)
├── Dockerfile            # multi-stage сборка backend-образа
└── app/
    ├── main.py           # создание FastAPI-приложения (create_app)
    ├── api/              # HTTP-слой: роутеры, зависимости, обработчики ошибок
    │   ├── deps.py       # DI: сессия БД, текущий пользователь
    │   ├── errors.py     # глобальные exception-handlers
    │   ├── router.py     # сборка всех роутеров под /api
    │   └── v1/           # эндпоинты: auth, users, listings, exchanges, chat, …
    ├── core/             # настройки приложения (pydantic-settings)
    ├── crud/             # запросы к БД (репозиторный слой)
    ├── db/               # engine, сессии, базовый класс моделей
    ├── logging/          # конфиг логирования и middleware
    ├── models/           # ORM-модели SQLAlchemy
    ├── policies/         # бизнес-правила (например, правила переписки)
    ├── schemas/          # Pydantic-схемы запросов/ответов
    ├── services/         # бизнес-логика (auth, обмены, профили)
    └── ws/               # менеджер WebSocket-соединений чата
```

## Карта переменных окружения

Все настройки читаются из `.env` в корне репозитория с префиксом `SSN_`
(см. `backend/app/core/settings.py`). Значения в таблице — демонстрационные/безопасные.

| Переменная | Тип | Назначение | Пример (безопасный) |
| --- | --- | --- | --- |
| `SSN_ENVIRONMENT` | string | Окружение запуска (`local` / `production`). Влияет на режим отладки и строгость настроек | `local` |
| `SSN_SECRET_KEY` | string | Секрет для подписи JWT-токенов. В проде — длинная случайная строка | `change-me-in-production` |
| `SSN_DATABASE_URL` | string (DSN) | Строка подключения к PostgreSQL (драйвер asyncpg) | `postgresql+asyncpg://postgres:postgres@localhost:5432/skillshare` |
| `SSN_REDIS_URL` | string (DSN) | Адрес Redis (кэш/брокер, задел на следующий спринт) | `redis://localhost:6379/0` |
| `SSN_PUBLIC_BASE_URL` | URL \| пусто | Внешний базовый URL приложения для генерации абсолютных ссылок | `https://skillshare.example.com` |

> Реальные пароли и ключи в репозиторий не коммитятся. `.env` хранится локально и
> добавлен в `.gitignore`; в репозитории лежит только `.env.example` с шаблонными значениями.

## Быстрый старт (локально)

Требования: Python 3.12+, [`uv`](https://astral.sh/uv/)

Все команды выполняются **из корня репозитория** (uv-проект и `.env` теперь там):

```bash
cp .env.example .env       # один раз — создать локальный .env
uv sync
uv run uvicorn main:app --reload
```

Открыть:
- `http://localhost:8000/` (SSR страница)
- `http://localhost:8000/api/v1/health` (healthcheck)

`uv` сам создаёт и поддерживает виртуальное окружение в `.venv/` — отдельную
команду `python -m venv` выполнять не нужно. Чтобы войти в окружение вручную:
`source .venv/bin/activate` (Linux/macOS) или `.venv\Scripts\activate` (Windows).

### Frontend (dev-режим)

```bash
cd frontend
npm install
npm run dev          # Vite dev-сервер на http://localhost:5173
npm run lint         # ESLint
```

### Ruff

```bash
uv run ruff check backend
uv run ruff format backend
```

## Запуск через Docker

### Полный стек (backend + frontend + postgres)

```bash
docker compose --profile full up --build
```

### Только backend + postgres (без frontend)

```bash
docker compose up --build
```

### Остановка

```bash
docker compose --profile full down
```

## Миграции (Alembic)

Перед миграциями убедитесь, что поднят Postgres и корректен `SSN_DATABASE_URL`
(берётся из `.env` в корне; дефолт указывает на `localhost:5432`).

`alembic.ini` живёт в `backend/`, поэтому команды Alembic запускаются из этой папки:

```bash
cd backend
uv run alembic revision --autogenerate -m "init"
uv run alembic upgrade head
```
