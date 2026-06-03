from datetime import datetime

from pydantic import BaseModel

from app.models import ChatStatus


class ChatRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    exchange_id: int
    status: ChatStatus
    created_at: datetime
    # Сообщения загружаются отдельно через /api/v1/chat/{chat_id}/messages
