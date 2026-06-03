from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_pass(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("Пароль должен содержать минимум 10 символов")
        return v


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    # Bearer — это тип токена в стандарте OAuth2.
    # Означает "предъявитель" — кто предъявил токен, тот и авторизован.
    token_type: str = "bearer"


class UserProfile(BaseModel):
    """Полный профиль текущего пользователя."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    avatar_url: str | None
    rating: float
    role: str
    # Профиль считается заполненным если есть имя и хотя бы один навык
    # Это поле вычисляется на фронте на основе full_name и навыков


class UserUpdate(BaseModel):
    """Поля которые пользователь может изменить сам."""

    full_name: str | None = None
    avatar_url: str | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_pass(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("Пароль должен содержать минимум 10 символов")
        return v


class UserSkillOffered(BaseModel):
    skill_id: int
    level: int  # 1-3


class UserSkillWanted(BaseModel):
    skill_id: int
    desired_level: int  # 1-3


class UserSkillsPayload(BaseModel):
    """Полная замена навыков пользователя."""

    offered: list[UserSkillOffered] = []
    wanted: list[UserSkillWanted] = []
