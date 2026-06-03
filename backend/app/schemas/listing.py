from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.listing import ListingInterestStatus, ListingStatus


class ListingCreate(BaseModel):
    title: str
    description: str | None = None
    offering_summary: str
    seeking_summary: str
    status: ListingStatus = ListingStatus.published


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    title: str
    description: str | None
    offering_summary: str
    seeking_summary: str
    status: ListingStatus
    created_at: datetime
    author_full_name: str | None = None


class ListingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    offering_summary: str | None = None
    seeking_summary: str | None = None
    status: ListingStatus | None = None


class ListingInterestCreate(BaseModel):
    message: str | None = None


class ListingInterestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    responder_id: int
    message: str | None
    status: ListingInterestStatus
    created_at: datetime


class ListingInterestDetailOut(BaseModel):
    """Отклик с присоединёнными данными объявления и автора отклика."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    responder_id: int
    message: str | None
    status: ListingInterestStatus
    created_at: datetime
    listing_title: str
    responder_full_name: str | None
