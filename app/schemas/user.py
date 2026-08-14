from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None


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
    current_password: str
    new_password: str