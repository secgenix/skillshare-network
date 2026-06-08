from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.user import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth import login_user, register_user

router = APIRouter(prefix="/auth", tags=["Auth"])
DB = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
    responses={
        201: {"description": "Пользователь создан"},
        409: {"description": "Пользователь с таким email уже зарегистрирован"},
        422: {"description": "Ошибка валидации входных данных"},
    },
)
async def register(data: UserRegister, db: DB) -> UserResponse:
    """Создаёт аккаунт по email, паролю и имени.

    Пароль хешируется (bcrypt) и в открытом виде не хранится. Email уникален:
    повторная регистрация на занятый адрес возвращает **409 Conflict**.
    """
    user = await register_user(db, data)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Аутентификация и выдача JWT",
    responses={
        200: {"description": "Успешный вход, возвращён access_token"},
        401: {"description": "Неверный пароль или email"},
        422: {"description": "Ошибка валидации входных данных"},
    },
)
async def login(data: UserLogin, db: DB) -> TokenResponse:
    """Проверяет учётные данные и возвращает JWT access-токен.

    Токен подписывается `SSN_SECRET_KEY` (HS256) и действует 24 часа.
    Используйте его в заголовке `Authorization: Bearer <token>`.
    """
    token = await login_user(db, data)
    return TokenResponse(access_token=token)
