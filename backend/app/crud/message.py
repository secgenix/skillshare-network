from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.chat import get_chat_by_exchange
from app.models import Message


async def get_messages(db: AsyncSession, chat_id: int) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id, Message.is_deleted.is_(False))
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


async def get_messages_by_exchange(db: AsyncSession, exchange_id: int) -> list[Message]:
    chat = await get_chat_by_exchange(db, exchange_id)
    if chat is None:
        return []
    return await get_messages(db, chat.id)


async def create_chat_message(
    db: AsyncSession,
    chat_id: int,
    sender_id: int,
    content: str | None,
    media_url: str | None = None,
) -> Message:
    msg = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        content=content,
        media_url=media_url,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    return msg


async def edit_message(db: AsyncSession, message: Message, content: str) -> Message:
    message.content = content
    message.edited_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(message)
    return message


async def soft_delete_message(db: AsyncSession, message: Message) -> Message:
    message.is_deleted = True
    await db.flush()
    await db.refresh(message)
    return message
