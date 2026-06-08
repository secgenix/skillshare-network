from __future__ import annotations

from pathlib import Path

from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень репозитория: settings.py лежит в backend/app/core/, поэтому поднимаемся
# на 4 уровня. Абсолютный путь к .env позволяет читать его из любой рабочей
# директории (например, при запуске Alembic из backend/).
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV, env_prefix="SSN_", extra="ignore")

    app_name: str = "SkillShare Network"
    environment: str = "local"
    # "change-me" — дефолтное значение только для разработки.
    # В продакшене обязательно меняется на длинную случайную строку
    secret_key: str = "change-me"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/skillshare"
    redis_url: str = "redis://localhost:6379/0"

    # AnyUrl — специальный тип Pydantic,
    # который проверяет что строка является валидным URL
    # (есть протокол, домен и т.д.).
    public_base_url: AnyUrl | None = None


settings = Settings()
