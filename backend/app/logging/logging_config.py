from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Каталог логов в корне репозитория (backend/app/logging/ -> parents[3]).
# logs/ добавлен в .gitignore: файлы логов живут только локально/на сервере.
LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_FILE = LOG_DIR / "app.log"

# Ротация: один файл до 10 МБ, храним до 5 архивных копий.
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

# Поля, которые middleware кладёт в запись через extra=... (контекст HTTP-запроса).
REQUEST_FIELDS = ("method", "path", "status_code", "duration")

# ANSI-цвета уровня (только для интерактивной консоли).
LEVEL_COLORS = {
    "DEBUG": "\033[36m",       # cyan
    "INFO": "\033[32m",        # green
    "WARNING": "\033[33m",     # yellow
    "ERROR": "\033[31m",       # red
    "CRITICAL": "\033[1;37;41m",  # bold white on red
}
RESET = "\033[0m"


class ReadableFormatter(logging.Formatter):
    """Единый формат: [Дата] [Уровень] [файл:строка] - сообщение.

    На консоли уровень подсвечивается цветом; в файл пишется без ANSI-кодов.
    Контекст HTTP-запроса (метод/путь/код/длительность) добавляется компактно.
    """

    def __init__(self, *, color: bool) -> None:
        super().__init__()
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record)  # с миллисекундами: 2026-06-08 11:36:26,956
        location = f"{record.filename}:{record.lineno}"
        message = record.getMessage()

        if hasattr(record, "method"):
            status = getattr(record, "status_code", "?")
            message += f" | {record.method} {record.path} -> {status}"
            duration = getattr(record, "duration", None)
            if duration is not None:
                message += f" ({duration * 1000:.1f} ms)"

        level = record.levelname
        if self.color and (color := LEVEL_COLORS.get(level)):
            level = f"{color}{level}{RESET}"

        line = f"[{timestamp}] [{level}] [{location}] - {message}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


def _console_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    # Цвет только в реальном терминале; при сборе логов в Docker/файл ANSI не нужен.
    handler.setFormatter(ReadableFormatter(color=sys.stdout.isatty()))
    return handler


def _file_handler() -> logging.Handler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(ReadableFormatter(color=False))
    return handler


def setup_logging() -> None:
    """Настраивает два независимых канала вывода: консоль и файл с ротацией."""
    logging.basicConfig(
        level=logging.INFO,
        handlers=[_console_handler(), _file_handler()],
        force=True,
    )

    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
