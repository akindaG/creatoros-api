from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ScheduleRequest(BaseModel):
    schedule_time: datetime
    platform: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: UUID
    post_id: UUID
    schedule_time: datetime
    publish_state: str
    platform: str

    class Config:
        from_attributes = True


class CalendarItem(BaseModel):
    schedule_id: UUID
    post_id: UUID
    title: str
    platform: str
    status: str
    schedule_time: datetime
