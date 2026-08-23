from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SocialAccountCreate(BaseModel):
    platform: str = Field(min_length=2, max_length=20)
    account_name: str = Field(min_length=1, max_length=255)
    username: Optional[str] = Field(default=None, max_length=255)
    access_token: str = Field(min_length=1, max_length=10000)
    refresh_token: Optional[str] = Field(default=None, max_length=10000)
    token_expires_at: Optional[datetime] = None


class SocialAccountResponse(BaseModel):
    id: UUID
    platform: str
    account_name: str
    username: Optional[str] = None
    created_at: datetime
    status: str

    class Config:
        from_attributes = True
