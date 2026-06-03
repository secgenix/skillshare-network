from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.review import Review
from app.models.skill import Skill, UserSkillsOffered, UserSkillsWanted
from app.models.user import User
from app.schemas.exchange import ReviewOut
from app.schemas.user import PasswordChangeRequest, UserProfile, UserSkillsPayload, UserUpdate
from app.services.auth import hash_password, verify_password
from app.services.user import cancel_user_exchanges

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: CurrentUser) -> User:
    """Возвращает профиль текущего авторизованного пользователя."""
    return current_user


@router.patch("/me", response_model=UserProfile)
async def update_me(
    payload: UserUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> User:
    """Обновляет имя и/или аватар текущего пользователя."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip() or None
    if payload.avatar_url is not None:
        current_user.avatar_url = payload.avatar_url.strip() or None
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.put("/me/skills")
async def update_my_skills(
    payload: UserSkillsPayload,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """
    Полностью заменяет навыки пользователя.
    offered: [{skill_id, level}]
    wanted:  [{skill_id, desired_level}]
    """
    # Проверяем что все skill_id существуют
    all_ids = {s.skill_id for s in payload.offered} | {s.skill_id for s in payload.wanted}
    if all_ids:
        existing = set(
            await db.scalars(
                select(Skill.id).where(Skill.id.in_(all_ids), Skill.is_deleted.is_(False))
            )
        )
        missing = all_ids - existing
        if missing:
            raise HTTPException(status_code=400, detail=f"Unknown skill ids: {sorted(missing)}")

    # Удаляем старые записи
    old_offered = list(
        await db.scalars(
            select(UserSkillsOffered).where(UserSkillsOffered.user_id == current_user.id)
        )
    )
    for row in old_offered:
        await db.delete(row)

    old_wanted = list(
        await db.scalars(
            select(UserSkillsWanted).where(UserSkillsWanted.user_id == current_user.id)
        )
    )
    for row in old_wanted:
        await db.delete(row)

    await db.flush()

    # Добавляем новые
    for s in payload.offered:
        db.add(UserSkillsOffered(user_id=current_user.id, skill_id=s.skill_id, level=s.level))
    for s in payload.wanted:
        db.add(
            UserSkillsWanted(
                user_id=current_user.id, skill_id=s.skill_id, desired_level=s.desired_level
            )
        )

    await db.flush()
    return {"ok": True}


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Смена пароля текущего пользователя."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    current_user.password_hash = hash_password(payload.new_password)
    await db.flush()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Мягкое удаление пользователя с отменой всех активных сделок."""
    await cancel_user_exchanges(db, current_user.id)

    current_user.is_deleted = True
    current_user.deleted_at = datetime.now(UTC)
    await db.flush()


@router.get("/me/reviews", response_model=list[ReviewOut])
async def get_my_reviews(
    db: DbSession,
    current_user: CurrentUser,
) -> list[ReviewOut]:
    """Отзывы полученные текущим пользователем."""
    reviews = list(
        await db.scalars(
            select(Review)
            .where(
                Review.reviewed_id == current_user.id,
                Review.is_deleted.is_(False),
                Review.is_hidden.is_(False),
            )
            .order_by(Review.id.desc())
            .limit(20)
        )
    )
    reviewer_ids = {r.reviewer_id for r in reviews}
    name_map: dict[int, str | None] = {}
    if reviewer_ids:
        rows = list(
            await db.execute(select(User.id, User.full_name).where(User.id.in_(reviewer_ids)))
        )
        name_map = {r.id: r.full_name for r in rows}

    return [
        ReviewOut.model_validate(r).model_copy(
            update={"reviewer_name": name_map.get(r.reviewer_id)}
        )
        for r in reviews
    ]


@router.get("/me/skills")
async def get_my_skills(
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Возвращает текущие навыки пользователя."""
    offered_rows = list(
        await db.execute(
            select(UserSkillsOffered, Skill)
            .join(Skill, Skill.id == UserSkillsOffered.skill_id)
            .where(UserSkillsOffered.user_id == current_user.id)
        )
    )
    wanted_rows = list(
        await db.execute(
            select(UserSkillsWanted, Skill)
            .join(Skill, Skill.id == UserSkillsWanted.skill_id)
            .where(UserSkillsWanted.user_id == current_user.id)
        )
    )
    return {
        "offered": [
            {"skill_id": r.skill_id, "skill_name": s.name, "level": r.level}
            for r, s in offered_rows
        ],
        "wanted": [
            {"skill_id": r.skill_id, "skill_name": s.name, "desired_level": r.desired_level}
            for r, s in wanted_rows
        ],
    }
