from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.listing import Listing, ListingInterest, ListingInterestStatus, ListingStatus
from app.models.user import User
from app.schemas.listing import (
    ListingCreate,
    ListingInterestCreate,
    ListingInterestDetailOut,
    ListingInterestOut,
    ListingOut,
    ListingUpdate,
)

router = APIRouter(prefix="/listings", tags=["listings"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def listing_to_out(listing: Listing, author_full_name: str | None) -> ListingOut:
    """Собирает ListingOut из ORM-объекта, подмешивая имя автора из JOIN."""
    return ListingOut.model_validate(listing).model_copy(
        update={"author_full_name": author_full_name}
    )


@router.post(
    "",
    response_model=ListingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать объявление",
    responses={
        201: {"description": "Объявление создано"},
        401: {"description": "Требуется авторизация"},
        422: {"description": "Ошибка валидации полей"},
    },
)
async def create_listing(
    payload: ListingCreate, db: DbSession, current_user: CurrentUser
) -> ListingOut:
    """Публикует объявление текущего пользователя: что он предлагает и что ищет взамен."""
    listing = Listing(
        author_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        offering_summary=payload.offering_summary.strip(),
        seeking_summary=payload.seeking_summary.strip(),
        status=payload.status,
    )
    db.add(listing)
    current_user.last_active_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(listing)
    return listing_to_out(listing, current_user.full_name)


@router.get(
    "/me/incoming-interests",
    response_model=list[ListingInterestDetailOut],
    summary="Входящие отклики на мои объявления",
    responses={401: {"description": "Требуется авторизация"}},
)
async def get_my_incoming_interests(
    db: DbSession, current_user: CurrentUser
) -> list[ListingInterestDetailOut]:
    """Все ожидающие (`pending`) отклики на объявления текущего пользователя."""
    rows = await db.execute(
        select(ListingInterest, Listing.title, User.full_name)
        .join(Listing, Listing.id == ListingInterest.listing_id)
        .join(User, User.id == ListingInterest.responder_id)
        .where(
            Listing.author_id == current_user.id,
            ListingInterest.status == ListingInterestStatus.pending,
        )
        .order_by(ListingInterest.created_at.desc())
    )
    return [
        ListingInterestDetailOut(
            id=interest.id,
            listing_id=interest.listing_id,
            responder_id=interest.responder_id,
            message=interest.message,
            status=interest.status,
            created_at=interest.created_at,
            listing_title=title,
            responder_full_name=full_name,
        )
        for interest, title, full_name in rows.all()
    ]


@router.patch(
    "/{listing_id}",
    response_model=ListingOut,
    summary="Редактировать объявление",
    responses={
        200: {"description": "Объявление обновлено"},
        400: {"description": "Обязательное поле передано пустым"},
        403: {"description": "Редактировать может только автор"},
        404: {"description": "Объявление не найдено"},
    },
)
async def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ListingOut:
    """Частично обновляет объявление. Менять может только его автор."""
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    if listing.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только автор может редактировать объявление")

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Заголовок не может быть пустым")
        listing.title = title
    if payload.description is not None:
        listing.description = payload.description.strip() or None
    if payload.offering_summary is not None:
        offering = payload.offering_summary.strip()
        if not offering:
            raise HTTPException(status_code=400, detail="Поле «предлагаю» не может быть пустым")
        listing.offering_summary = offering
    if payload.seeking_summary is not None:
        seeking = payload.seeking_summary.strip()
        if not seeking:
            raise HTTPException(status_code=400, detail="Поле «ищу» не может быть пустым")
        listing.seeking_summary = seeking
    if payload.status is not None:
        listing.status = payload.status

    current_user.last_active_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(listing)
    return listing_to_out(listing, current_user.full_name)


@router.get(
    "/{listing_id}/interests",
    response_model=list[ListingInterestDetailOut],
    summary="Отклики на конкретное объявление",
    responses={
        403: {"description": "Отклики видит только автор объявления"},
        404: {"description": "Объявление не найдено"},
    },
)
async def get_listing_interests(
    listing_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ListingInterestDetailOut]:
    """Ожидающие отклики на объявление. Доступно только автору объявления."""
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Объявление не найдено")
    if listing.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Только автор объявления видит отклики")

    rows = await db.execute(
        select(ListingInterest, Listing.title, User.full_name)
        .join(Listing, Listing.id == ListingInterest.listing_id)
        .join(User, User.id == ListingInterest.responder_id)
        .where(
            ListingInterest.listing_id == listing_id,
            ListingInterest.status == ListingInterestStatus.pending,
        )
        .order_by(ListingInterest.created_at.desc())
    )
    return [
        ListingInterestDetailOut(
            id=interest.id,
            listing_id=interest.listing_id,
            responder_id=interest.responder_id,
            message=interest.message,
            status=interest.status,
            created_at=interest.created_at,
            listing_title=title,
            responder_full_name=full_name,
        )
        for interest, title, full_name in rows.all()
    ]


@router.get(
    "",
    response_model=list[ListingOut],
    summary="Лента объявлений",
    responses={200: {"description": "Список объявлений с именами авторов"}},
)
async def get_listings(
    db: DbSession,
    status_filter: Annotated[ListingStatus | None, Query(alias="status")] = ListingStatus.published,
    author_id: int | None = None,
) -> list[ListingOut]:
    """Возвращает объявления с фильтрами по статусу (`status`) и автору (`author_id`).

    По умолчанию показываются только опубликованные объявления активных пользователей.
    """
    stmt = (
        select(Listing, User.full_name)
        .join(User, User.id == Listing.author_id)
        .where(User.is_deleted.is_(False))
    )
    if status_filter is not None:
        stmt = stmt.where(Listing.status == status_filter)
    if author_id is not None:
        stmt = stmt.where(Listing.author_id == author_id)
    stmt = stmt.order_by(Listing.created_at.desc())
    rows = await db.execute(stmt)
    return [listing_to_out(listing, full_name) for listing, full_name in rows.all()]


@router.post(
    "/{listing_id}/interests",
    response_model=ListingInterestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Откликнуться на объявление",
    responses={
        201: {"description": "Отклик создан"},
        400: {"description": "Нельзя откликнуться на собственное объявление"},
        404: {"description": "Объявление не найдено или снято с публикации"},
        409: {"description": "Отклик от этого пользователя уже существует"},
    },
)
async def create_listing_interest(
    listing_id: int,
    payload: ListingInterestCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ListingInterest:
    """Создаёт отклик текущего пользователя на чужое опубликованное объявление."""
    listing = await db.get(Listing, listing_id)
    if listing is None or listing.status != ListingStatus.published:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.author_id == current_user.id:
        raise HTTPException(status_code=400, detail="Author cannot respond to own listing")

    interest = ListingInterest(
        listing_id=listing_id,
        responder_id=current_user.id,
        message=payload.message.strip() if payload.message else None,
        status=ListingInterestStatus.pending,
    )
    db.add(interest)
    current_user.last_active_at = datetime.now(UTC)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Interest already exists") from exc

    await db.refresh(interest)
    return interest
