from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat, ChatStatus
from app.models.exchange import Exchange, ExchangeParticipant, ExchangeStatus
from app.models.listing import Listing, ListingStatus
from app.models.message import Message
from app.models.user import User
from app.schemas.admin import (
    AdminExchangeOut,
    ExchangeStatusPatch,
    ListingStatusPatch,
    UserStatusPatch,
)

logger = logging.getLogger("app.admin")


def log_admin_action(admin: User, action: str, target: str, target_id: int | None = None) -> None:
    if target_id:
        logger.info(
            "[ADMIN] admin_id=%d action=%s target=%s target_id=%d",
            admin.id,
            action,
            target,
            target_id,
        )
    else:
        logger.info("[ADMIN] admin_id=%d action=%s target=%s", admin.id, action, target)


async def get_users(db: AsyncSession, admin: User, limit: int, offset: int) -> list[User]:
    log_admin_action(admin, "list_users", "user")
    result = await db.scalars(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def get_user(db: AsyncSession, admin: User, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    log_admin_action(admin, "view_user", "user", user.id)
    return user


async def update_user_status(
    db: AsyncSession, admin: User, user_id: int, payload: UserStatusPatch
) -> User:
    user = await get_user(db=db, admin=admin, user_id=user_id)

    if user.id == admin.id:
        if payload.is_deleted is True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin cannot block himself",
            )
        if payload.role is not None and payload.role != admin.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin cannot change his own role",
            )

    if payload.is_deleted is not None:
        user.is_deleted = payload.is_deleted
        user.deleted_at = datetime.now(UTC) if payload.is_deleted else None

    if payload.role is not None:
        user.role = payload.role

    await db.flush()
    await db.refresh(user)
    log_admin_action(admin, "update_user_status", "user", user.id)
    return user


async def get_listings(db: AsyncSession, admin: User, limit: int, offset: int) -> list[Listing]:
    log_admin_action(admin, "list_listings", "listing")
    result = await db.scalars(
        select(Listing).order_by(Listing.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def update_listing_status(
    db: AsyncSession, admin: User, listing_id: int, payload: ListingStatusPatch
) -> Listing:
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    listing.status = payload.status
    await db.flush()
    await db.refresh(listing)
    log_admin_action(admin, "update_listing_status", "listing", listing.id)
    return listing


async def remove_listing(db: AsyncSession, admin: User, listing_id: int) -> None:
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    listing.status = ListingStatus.archived
    await db.flush()
    log_admin_action(admin, "archive_listing", "listing", listing.id)


async def get_exchanges(
    db: AsyncSession,
    admin: User,
    limit: int,
    offset: int,
    status_filter: ExchangeStatus | None = None,
) -> list[AdminExchangeOut]:
    log_admin_action(admin, "list_exchanges", "exchange")
    q = select(Exchange).order_by(Exchange.created_at.desc()).limit(limit).offset(offset)
    if status_filter is not None:
        q = q.where(Exchange.status == status_filter)
    exchanges = list(await db.scalars(q))
    if not exchanges:
        return []

    exchange_ids = [ex.id for ex in exchanges]

    # Батч-запрос участников
    participant_rows = list(
        await db.execute(
            select(ExchangeParticipant.exchange_id, ExchangeParticipant.user_id).where(
                ExchangeParticipant.exchange_id.in_(exchange_ids)
            )
        )
    )
    initiator_by_id = {ex.id: ex.initiator_id for ex in exchanges}
    partner_map: dict[int, int | None] = {ex.id: None for ex in exchanges}
    for exchange_id, user_id in participant_rows:
        if user_id != initiator_by_id.get(exchange_id):
            partner_map[exchange_id] = user_id

    # Батч-запрос имён
    all_user_ids = set(initiator_by_id.values()) | {pid for pid in partner_map.values() if pid}
    user_name_map: dict[int, str | None] = {}
    if all_user_ids:
        name_rows = list(
            await db.execute(select(User.id, User.full_name).where(User.id.in_(all_user_ids)))
        )
        user_name_map = {r.id: r.full_name for r in name_rows}

    result = []
    for ex in exchanges:
        partner_id = partner_map.get(ex.id)
        result.append(
            AdminExchangeOut.model_validate(ex).model_copy(
                update={
                    "initiator_name": user_name_map.get(ex.initiator_id),
                    "partner_id": partner_id,
                    "partner_name": user_name_map.get(partner_id) if partner_id else None,
                }
            )
        )
    return result


async def update_exchange_status(
    db: AsyncSession, admin: User, exchange_id: int, payload: ExchangeStatusPatch
) -> Exchange:
    exchange = await db.get(Exchange, exchange_id)
    if exchange is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exchange not found")

    exchange.status = payload.status

    if payload.status == ExchangeStatus.cancelled:
        exchange.is_deleted = True
        exchange.deleted_at = datetime.now(UTC)
        exchange.completed_at = None

    if payload.status == ExchangeStatus.completed:
        exchange.completed_at = datetime.now(UTC)
        exchange.completed_by_initiator = True
        exchange.completed_by_partner = True

    await db.flush()
    await db.refresh(exchange)
    log_admin_action(admin, "update_exchange_status", "exchange", exchange.id)
    return exchange


async def cancel_exchange(db: AsyncSession, admin: User, exchange_id: int) -> None:
    await update_exchange_status(
        db=db,
        admin=admin,
        exchange_id=exchange_id,
        payload=ExchangeStatusPatch(status=ExchangeStatus.cancelled),
    )
    log_admin_action(admin, "cancel_exchange", "exchange", exchange_id)


async def get_chats(db: AsyncSession, admin: User, limit: int, offset: int) -> list[Chat]:
    log_admin_action(admin, "list_chats", "chat")
    result = await db.scalars(
        select(Chat).order_by(Chat.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def get_chat_messages(
    db: AsyncSession, admin: User, chat_id: int, limit: int, offset: int
) -> list[Message]:
    chat = await db.get(Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    result = await db.scalars(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    log_admin_action(admin, "view_chat_messages", "chat", chat_id)
    return list(result)


async def close_chat(db: AsyncSession, admin: User, chat_id: int) -> None:
    chat = await db.get(Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    chat.status = ChatStatus.closed
    await db.flush()
    log_admin_action(admin, "close_chat", "chat", chat.id)
