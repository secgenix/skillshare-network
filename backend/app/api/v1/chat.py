from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.crud import chat as chat_crud
from app.crud import message as message_crud
from app.db.session import get_db_session
from app.models import Message
from app.models.user import User
from app.schemas.chat import ChatRead
from app.schemas.message import MessageRead, MessageUpdate

router = APIRouter(prefix="/chat", tags=["chat"])
DB = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/exchanges/{exchange_id}", response_model=ChatRead)
async def get_chat(exchange_id: int, db: DB):
    chat = await chat_crud.get_chat_by_exchange(db, exchange_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return chat


@router.get("/exchanges/{exchange_id}/messages", response_model=list[MessageRead])
async def list_messages(exchange_id: int, db: DB):
    return await message_crud.get_messages_by_exchange(db, exchange_id)


@router.patch("/exchanges/{exchange_id}/messages/{message_id}", response_model=MessageRead)
async def edit_message(exchange_id: int, message_id: int, body: MessageUpdate, db: DB):
    chat = await chat_crud.get_chat_by_exchange(db, exchange_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    result = await db.execute(
        select(Message).where(Message.chat_id == chat.id, Message.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    return await message_crud.edit_message(db, msg, body.content)


@router.delete("/exchanges/{exchange_id}/messages/{message_id}", response_model=MessageRead)
async def delete_message(exchange_id: int, message_id: int, db: DB):
    chat = await chat_crud.get_chat_by_exchange(db, exchange_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    result = await db.execute(
        select(Message).where(Message.chat_id == chat.id, Message.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    return await message_crud.soft_delete_message(db, msg)
