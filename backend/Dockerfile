# ВАЖНО: build context — корень репозитория (см. docker-compose*.yml),
# поэтому пути источников указываются с префиксом backend/.
#
# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Копируем только venv из builder — без uv, curl и прочего мусора
COPY --from=builder /app/.venv /app/.venv

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini backend/gunicorn_conf.py backend/entrypoint.sh ./

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.main:app"]
