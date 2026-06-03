"""Точка входа для запуска приложения из корня проекта.

Сам код приложения живёт в ``backend/app``. Здесь мы добавляем каталог
``backend`` в путь импорта и реэкспортируем готовый объект FastAPI, чтобы
проект можно было запускать прямо из корня:

    uv run uvicorn main:app --reload

Переменные окружения берутся из ``.env`` в корне репозитория (pydantic-settings
читает файл относительно текущего рабочего каталога).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Делаем пакет ``app`` (он лежит в backend/) импортируемым из корня.
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402  (импорт после правки sys.path — это намеренно)

__all__ = ["app"]
