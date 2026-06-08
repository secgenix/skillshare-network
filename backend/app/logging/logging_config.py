from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

# Каталог логов в корне репозитория (backend/app/logging/ -> parents[3]).
# logs/ добавлен в .gitignore: файлы логов живут только локально/на сервере.
LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_FILE = LOG_DIR / "app.log"

# Ротация: один файл до 10 МБ, храним до 5 архивных копий.
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

# Человекочитаемый формат для файла: [время] [уровень] [файл:строка] - сообщение.
FILE_FORMAT = "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s"


class JsonFormatter(logging.Formatter):
    """Структурированный JSON-формат для stdout (удобно для сбора в Docker)."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "source": f"{record.filename}:{record.lineno}",
            "message": record.getMessage(),
        }

        for field in (
            "request_id",
            "method",
            "path",
            "query_params",
            "status_code",
            "duration",
            "client_ip",
            "user_agent",
        ):
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def _console_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    return handler


def _file_handler() -> logging.Handler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(FILE_FORMAT))
    return handler


def setup_logging() -> None:
    """Настраивает два независимых канала вывода: консоль (JSON) и файл с ротацией."""
    logging.basicConfig(
        level=logging.INFO,
        handlers=[_console_handler(), _file_handler()],
        force=True,
    )

    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
