from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    profile_image: Optional[str] = Field(default=None, max_length=2048)
    bio: Optional[str] = Field(default=None, max_length=500)


class UserProfileResponse(BaseModel):
    id: UUID
    name: str
    email: str
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    role: str

    class Config:
        from_attributes = True


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
