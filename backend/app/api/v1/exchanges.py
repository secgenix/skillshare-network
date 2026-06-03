from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.crud.chat import create_chat, get_chat_by_exchange
from app.models.exchange import Exchange, ExchangeParticipant, ExchangeStatus
from app.models.listing import Listing, ListingInterest, ListingInterestStatus
from app.models.message import Message
from app.models.review import Review
from app.models.user import User
from app.policies.exchange_messaging import can_post_in_deal_chat
from app.schemas.exchange import (
    AcceptInterestRequest,
    DirectExchangeRequest,
    ExchangeOut,
    ExchangeStatusUpdate,
    MessageCreate,
    MessageOut,
    ReviewCreate,
    ReviewOut,
)
from app.ws.manager import manager

router = APIRouter(prefix="/exchanges", tags=["exchanges"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


async def _get_exchange_participant_ids(db: AsyncSession, exchange: Exchange) -> set[int]:
    # Получаем всех участников через ExchangeParticipant
    participant_ids = list(
        await db.scalars(
            select(ExchangeParticipant.user_id).where(
                ExchangeParticipant.exchange_id == exchange.id
            )
        )
    )
    # Добавляем инициатора на случай если записи participants еще нет
    participants: set[int] = set(participant_ids) if participant_ids else {exchange.initiator_id}
    return participants


async def _get_partner_user_id(db: AsyncSession, exchange: Exchange) -> int | None:
    # Получаем ID партнера (не инициатора) через ExchangeParticipant
    participant_ids = list(
        await db.scalars(
            select(ExchangeParticipant.user_id).where(
                ExchangeParticipant.exchange_id == exchange.id
            )
        )
    )
    for pid in participant_ids:
        if pid != exchange.initiator_id:
            return pid
    # Fallback на ListingInterest если participants нет (legacy)
    if exchange.listing_id:
        return await db.scalar(
            select(ListingInterest.responder_id).where(
                ListingInterest.listing_id == exchange.listing_id,
                ListingInterest.status == ListingInterestStatus.accepted,
            )
        )
    return None


async def _require_exchange_member(db: AsyncSession, exchange: Exchange, user_id: int) -> None:
    participants = await _get_exchange_participant_ids(db, exchange)
    if user_id not in participants:
        raise HTTPException(status_code=403, detail="Only exchange members have access")


async def _broadcast_exchange_update(
    db: AsyncSession, exchange: Exchange, partner_id: int | None
) -> None:
    """Рассылает актуальное состояние сделки всем WS-клиентам чата."""
    from app.crud.chat import get_chat_by_exchange as _get_chat

    chat = await _get_chat(db, exchange.id)
    if chat is None:
        return
    partner_user = await db.get(User, partner_id) if partner_id else None
    out = ExchangeOut.model_validate(exchange).model_copy(
        update={
            "partner_id": partner_id,
            "partner_name": partner_user.full_name if partner_user else None,
        }
    )
    await manager.broadcast(
        chat.id,
        {
            "type": "exchange_update",
            "exchange": out.model_dump(mode="json"),
        },
    )


@router.post("/listing/{listing_id}/accept-interest", response_model=ExchangeOut)
async def accept_listing_interest(
    listing_id: int,
    payload: AcceptInterestRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Exchange:
    listing = await db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only listing author can accept interests")

    interest = await db.scalar(
        select(ListingInterest).where(
            ListingInterest.listing_id == listing_id,
            ListingInterest.responder_id == payload.responder_id,
        )
    )
    if interest is None:
        raise HTTPException(status_code=404, detail="Interest not found")

    existing = await db.scalar(
        select(Exchange).where(
            Exchange.listing_id == listing_id,
            Exchange.status.in_([ExchangeStatus.discussion, ExchangeStatus.active]),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Active exchange already exists for listing")

    all_interests = list(
        await db.scalars(select(ListingInterest).where(ListingInterest.listing_id == listing_id))
    )
    for item in all_interests:
        item.status = (
            ListingInterestStatus.accepted
            if item.responder_id == payload.responder_id
            else ListingInterestStatus.rejected
        )

    exchange = Exchange(
        initiator_id=current_user.id,
        listing_id=listing_id,
        status=ExchangeStatus.discussion,
        is_chain=False,
    )
    db.add(exchange)
    await db.flush()
    await db.refresh(exchange)

    # Создаем записи участников для обоих пользователей
    db.add(
        ExchangeParticipant(
            exchange_id=exchange.id,
            user_id=current_user.id,
            gives_skill_id=None,
            gets_skill_id=None,
        )
    )
    db.add(
        ExchangeParticipant(
            exchange_id=exchange.id,
            user_id=payload.responder_id,
            gives_skill_id=None,
            gets_skill_id=None,
        )
    )
    await db.flush()

    await create_chat(db, exchange.id)
    return exchange


@router.post("/direct", response_model=ExchangeOut)
async def create_direct_exchange(
    payload: DirectExchangeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ExchangeOut:
    """Начать прямой обмен через матчмейкинг (без листинга).
    Если активный/обсуждаемый обмен уже существует — возвращает его."""
    if payload.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot create exchange with yourself")

    target = await db.get(User, payload.target_user_id)
    if target is None or target.is_deleted:
        raise HTTPException(status_code=404, detail="User not found")

    # Ищем уже существующий активный/обсуждаемый обмен между двумя пользователями
    my_ex_ids = select(ExchangeParticipant.exchange_id).where(
        ExchangeParticipant.user_id == current_user.id
    )
    their_ex_ids = select(ExchangeParticipant.exchange_id).where(
        ExchangeParticipant.user_id == payload.target_user_id
    )
    existing = await db.scalar(
        select(Exchange).where(
            Exchange.id.in_(my_ex_ids),
            Exchange.id.in_(their_ex_ids),
            Exchange.status.in_([ExchangeStatus.discussion, ExchangeStatus.active]),
            Exchange.is_deleted.is_(False),
        )
    )
    if existing is not None:
        partner_id = (
            payload.target_user_id
            if existing.initiator_id == current_user.id
            else existing.initiator_id
        )
        return ExchangeOut.model_validate(existing).model_copy(
            update={
                "partner_id": partner_id,
                "partner_name": target.full_name,
            }
        )

    exchange = Exchange(
        initiator_id=current_user.id,
        listing_id=None,
        status=ExchangeStatus.discussion,
        is_chain=False,
    )
    db.add(exchange)
    await db.flush()
    await db.refresh(exchange)

    db.add(ExchangeParticipant(exchange_id=exchange.id, user_id=current_user.id))
    db.add(ExchangeParticipant(exchange_id=exchange.id, user_id=payload.target_user_id))
    await db.flush()

    await create_chat(db, exchange.id)

    return ExchangeOut.model_validate(exchange).model_copy(
        update={
            "partner_id": payload.target_user_id,
            "partner_name": target.full_name,
        }
    )


@router.get("", response_model=list[ExchangeOut])
async def get_my_exchanges(db: DbSession, current_user: CurrentUser) -> list[ExchangeOut]:
    # ID сделок, где пользователь — инициатор
    initiator_ids = set(
        await db.scalars(
            select(Exchange.id).where(
                Exchange.initiator_id == current_user.id,
                Exchange.is_deleted.is_(False),
            )
        )
    )
    # Получаем ID сделок где пользователь участник (через ExchangeParticipant)
    participant_ids = set(
        await db.scalars(
            select(ExchangeParticipant.exchange_id).where(
                ExchangeParticipant.user_id == current_user.id
            )
        )
    )
    # Fallback: получаем ID сделок где пользователь responder через ListingInterest (старые сделки)
    legacy_ids = set(
        await db.scalars(
            select(Exchange.id)
            .join(ListingInterest, ListingInterest.listing_id == Exchange.listing_id)
            .where(
                ListingInterest.responder_id == current_user.id,
                ListingInterest.status == ListingInterestStatus.accepted,
                Exchange.is_deleted.is_(False),
            )
        )
    )
    # Объединяем уникальные ID
    all_ids = initiator_ids | participant_ids | legacy_ids
    if not all_ids:
        return []
    # Получаем полные объекты
    exchanges = list(
        await db.scalars(
            select(Exchange).where(Exchange.id.in_(all_ids)).order_by(Exchange.created_at.desc())
        )
    )
    # Батч-запрос partner_id для всех сделок за один раз
    participant_rows = list(
        await db.execute(
            select(ExchangeParticipant.exchange_id, ExchangeParticipant.user_id).where(
                ExchangeParticipant.exchange_id.in_(all_ids)
            )
        )
    )
    # non_initiator_map: exchange_id → id участника-не-инициатора
    initiator_by_id = {ex.id: ex.initiator_id for ex in exchanges}
    non_initiator_map: dict[int, int | None] = {ex.id: None for ex in exchanges}
    for exchange_id, user_id in participant_rows:
        if user_id != initiator_by_id.get(exchange_id):
            non_initiator_map[exchange_id] = user_id

    # partner_id с точки зрения текущего пользователя:
    # — если я инициатор → партнёр = не-инициатор
    # — если я участник (не-инициатор) → партнёр = инициатор
    def perspective_partner(ex_id: int) -> int | None:
        if initiator_by_id.get(ex_id) == current_user.id:
            return non_initiator_map.get(ex_id)
        return initiator_by_id.get(ex_id)

    # Батч-запрос имён: нужны и инициаторы, и не-инициаторы
    all_user_ids = set(initiator_by_id.values()) | {
        pid for pid in non_initiator_map.values() if pid is not None
    }
    user_name_map: dict[int, str | None] = {}
    if all_user_ids:
        name_rows = list(
            await db.execute(select(User.id, User.full_name).where(User.id.in_(all_user_ids)))
        )
        user_name_map = {r.id: r.full_name for r in name_rows}

    return [
        ExchangeOut.model_validate(ex).model_copy(
            update={
                "partner_id": perspective_partner(ex.id),
                "partner_name": user_name_map.get(perspective_partner(ex.id)),
            }
        )
        for ex in exchanges
    ]


@router.post("/{exchange_id}/status", response_model=ExchangeOut)
async def update_exchange_status(
    exchange_id: int,
    payload: ExchangeStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Exchange:
    exchange = await db.get(Exchange, exchange_id)
    if exchange is None:
        raise HTTPException(status_code=404, detail="Exchange not found")
    await _require_exchange_member(db, exchange, current_user.id)

    allowed = {
        ExchangeStatus.discussion: {ExchangeStatus.active, ExchangeStatus.cancelled},
        ExchangeStatus.active: {ExchangeStatus.cancelled},
        ExchangeStatus.completed: set(),
        ExchangeStatus.cancelled: set(),
    }
    if payload.to not in allowed[exchange.status]:
        raise HTTPException(status_code=400, detail="Invalid status transition")

    exchange.status = payload.to
    if payload.to != ExchangeStatus.completed:
        exchange.completed_by_initiator = False
        exchange.completed_by_partner = False
        exchange.completed_at = None
        current_user.last_active_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(exchange)
    partner_id = await _get_partner_user_id(db, exchange)
    await _broadcast_exchange_update(db, exchange, partner_id)
    return exchange


@router.post("/{exchange_id}/request-start", response_model=ExchangeOut)
async def request_start_exchange(
    exchange_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Exchange:
    """Запрос на начало обмена (двухстороннее подтверждение)."""
    exchange = await db.get(Exchange, exchange_id)
    if exchange is None:
        raise HTTPException(status_code=404, detail="Exchange not found")
    await _require_exchange_member(db, exchange, current_user.id)

    if exchange.status != ExchangeStatus.discussion:
        raise HTTPException(status_code=400, detail="Can only request start from discussion status")

    partner_id = await _get_partner_user_id(db, exchange)
    if partner_id is None:
        raise HTTPException(status_code=400, detail="Cannot resolve second exchange member")

    is_initiator = current_user.id == exchange.initiator_id
    is_partner = current_user.id == partner_id

    if is_initiator:
        if exchange.started_by_initiator:
            raise HTTPException(status_code=400, detail="You already requested to start")
        exchange.started_by_initiator = True
    elif is_partner:
        if exchange.started_by_partner:
            raise HTTPException(status_code=400, detail="You already requested to start")
        exchange.started_by_partner = True
    else:
        raise HTTPException(status_code=403, detail="Only exchange members can request start")

    # Если оба подтвердили — переходим в active
    if exchange.started_by_initiator and exchange.started_by_partner:
        exchange.status = ExchangeStatus.active
        exchange.started_at = datetime.now(UTC)

    current_user.last_active_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(exchange)
    await _broadcast_exchange_update(db, exchange, partner_id)
    return exchange


@router.post("/{exchange_id}/confirm-completion", response_model=ExchangeOut)
async def confirm_exchange_completion(
    exchange_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Exchange:
    exchange = await db.get(Exchange, exchange_id)
    if exchange is None:
        raise HTTPException(status_code=404, detail="Exchange not found")
    await _require_exchange_member(db, exchange, current_user.id)

    if exchange.status != ExchangeStatus.active:
        raise HTTPException(status_code=400, detail="Only active exchanges can be completed")

    partner_id = await _get_partner_user_id(db, exchange)
    if partner_id is None:
        raise HTTPException(status_code=400, detail="Cannot resolve second exchange member")

    if current_user.id == exchange.initiator_id:
        exchange.completed_by_initiator = True
    elif current_user.id == partner_id:
        exchange.completed_by_partner = True
    else:
        raise HTTPException(status_code=403, detail="Only exchange members can confirm completion")

    if exchange.completed_by_initiator and exchange.completed_by_partner:
        exchange.status = ExchangeStatus.completed
        exchange.completed_at = datetime.now(UTC)
        current_user.last_active_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(exchange)
    await _broadcast_exchange_update(db, exchange, partner_id)
    return exchange


@router.get("/{exchange_id}/messages", response_model=list[MessageOut])
async def get_exchange_messages(
    exchange_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[Message]:
    exchange = await db.get(Exchange, exchange_id)
    if exchange is None:
        raise HTTPException(status_code=404, detail="Exchange not found")
    await _require_exchange_member(db, exchange, current_user.id)

    chat = await get_chat_by_exchange(db, exchange_id)
    if chat is None:
        chat = await create_chat(db, exchange_id)

    return list(
        await db.scalars(
            select(Message)
            .where(Message.chat_id == chat.id, Message.is_deleted.is_(False))
            .order_by(Message.created_at.asc())
        )
    )


@router.post(
    "/{exchange_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
async def post_exchange_message(
    exchange_id: int,
    payload: MessageCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Message:
    exchange = await db.get(Exchange, exchange_id)
    if exchange is None:
        raise HTTPException(status_code=404, detail="Exchange not found")
    await _require_exchange_member(db, exchange, current_user.id)

    if not can_post_in_deal_chat(exchange):
        raise HTTPException(status_code=400, detail="Exchange chat is read-only for current status")

    chat = await get_chat_by_exchange(db, exchange_id)
    if chat is None:
        chat = await create_chat(db, exchange_id)

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    message = Message(
        chat_id=chat.id,
        sender_id=current_user.id,
        content=content,
    )
    db.add(message)
    current_user.last_active_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(message)

    # WebSocket broadcast для real-time доставки
    await manager.broadcast(
        chat.id,
        {
            "id": message.id,
            "chat_id": message.chat_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "media_url": message.media_url,
            "created_at": message.created_at.isoformat(),
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "is_deleted": message.is_deleted,
        },
    )

    return message


@router.get("/{exchange_id}/reviews", response_model=list[ReviewOut])
async def get_exchange_reviews(
    exchange_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[ReviewOut]:
    exchange = await db.get(Exchange, exchange_id)
    if exchange is None:
        raise HTTPException(status_code=404, detail="Exchange not found")
    await _require_exchange_member(db, exchange, current_user.id)

    reviews = list(
        await db.scalars(
            select(Review).where(
                Review.exchange_id == exchange_id,
                Review.is_deleted.is_(False),
            )
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


@router.post(
    "/{exchange_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED
)
async def create_exchange_review(
    exchange_id: int,
    payload: ReviewCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Review:
    exchange = await db.get(Exchange, exchange_id)
    if exchange is None:
        raise HTTPException(status_code=404, detail="Exchange not found")
    await _require_exchange_member(db, exchange, current_user.id)

    if exchange.status != ExchangeStatus.completed:
        raise HTTPException(
            status_code=400, detail="Reviews are available only for completed exchanges"
        )
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be in range 1..5")

    partner_id = await _get_partner_user_id(db, exchange)
    if partner_id is None:
        raise HTTPException(status_code=400, detail="Cannot resolve review target")

    if current_user.id == exchange.initiator_id:
        reviewed_id = partner_id
    elif current_user.id == partner_id:
        reviewed_id = exchange.initiator_id
    else:
        raise HTTPException(status_code=403, detail="Only exchange members can review")

    review = Review(
        exchange_id=exchange.id,
        reviewer_id=current_user.id,
        reviewed_id=reviewed_id,
        rating=payload.rating,
        comment=payload.comment.strip() if payload.comment else None,
    )
    db.add(review)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="You have already submitted a review") from exc

    avg_rating = await db.scalar(
        select(func.avg(Review.rating)).where(
            Review.reviewed_id == reviewed_id,
            Review.is_deleted.is_(False),
            Review.is_hidden.is_(False),
        )
    )
    reviewed_user = await db.get(User, reviewed_id)
    if reviewed_user is not None and avg_rating is not None:
        reviewed_user.rating = float(avg_rating)
        await db.flush()

    await db.refresh(review)
    return review
