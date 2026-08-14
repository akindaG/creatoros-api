from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SocialAccountCreate(BaseModel):
    platform: str
    account_name: str
    username: Optional[str] = None
    access_token: str
    refresh_token: Optional[str] = None
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