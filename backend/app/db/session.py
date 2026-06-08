from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import settings

logger = logging.getLogger("app.db")

# Ошибки уровня соединения с СУБД — для них пишем CRITICAL со stack trace.
DB_CONNECTION_ERRORS = (OperationalError, InterfaceError, DBAPIError)

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def check_database_connection() -> bool:
    """Проверяет связь с PostgreSQL на старте. INFO при успехе, CRITICAL при сбое."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.critical(
            "Database connection FAILED at startup (host unreachable / wrong credentials)",
            exc_info=True,
        )
        return False
    logger.info("Database connection established")
    return True


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except DB_CONNECTION_ERRORS:
            logger.critical("Database failure during request", exc_info=True)
            await _safe_rollback(session)
            raise
        except Exception:
            await session.rollback()
            raise


async def _safe_rollback(session: AsyncSession) -> None:
    """Откат с защитой: при оборванном соединении сам rollback может упасть."""
    try:
        await session.rollback()
    except Exception:
        logger.error("Rollback failed after database error", exc_info=True)
