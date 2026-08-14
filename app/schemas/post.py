from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from uuid import UUID

from pydantic import BaseModel


class PostCreate(BaseModel):
    title: str
    caption: Optional[str] = None
    media_url: Optional[str] = None
    platform: str
    status: str = "draft"
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
    title: Optional[str] = None
    caption: Optional[str] = None
    media_url: Optional[str] = None
    platform: Optional[str] = None
    status: Optional[str] = None
    scheduled_time: Optional[datetime] = None