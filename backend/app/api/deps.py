"""Общие зависимости FastAPI (Depends)."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import get_db_session
from app.models.user import User

__all__ = ["get_db_session", "get_current_user"]

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    db: DbSession,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> User:
    """Валидирует Bearer JWT и возвращает текущего пользователя."""
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await db.scalar(select(User).where(User.id == int(user_id), User.is_deleted.is_(False)))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or blocked",
        )
    return user
