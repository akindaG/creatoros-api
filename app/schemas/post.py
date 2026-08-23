from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    caption: Optional[str] = Field(default=None, max_length=5000)
    media_url: Optional[str] = Field(default=None, max_length=4096)
    platform: str = Field(min_length=2, max_length=20)
    status: str = Field(default="draft", max_length=30)
    scheduled_time: Optional[datetime] = None


class PostResponse(BaseModel):
    id: UUID
    title: str
    caption: Optional[str]
    media_url: Optional[str]
    platform: str
    status: str
    scheduled_time: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class PostUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    caption: Optional[str] = Field(default=None, max_length=5000)
    media_url: Optional[str] = Field(default=None, max_length=4096)
    platform: Optional[str] = Field(default=None, max_length=20)
    status: Optional[str] = Field(default=None, max_length=30)
    scheduled_time: Optional[datetime] = None
