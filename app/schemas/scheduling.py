from datetime import datetime
from typing import Optional

from pydantic import Field
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScheduleRequest(BaseModel):
    schedule_time: datetime
    platform: Optional[str] = None


class MultiScheduleRequest(BaseModel):
    schedule_time: datetime
    platforms: list[str] = Field(min_length=1, max_length=2)


class ScheduleResponse(BaseModel):
    id: UUID
    post_id: UUID
    schedule_group_id: Optional[UUID] = None
    schedule_time: datetime
    publish_state: str
    platform: str

    model_config = ConfigDict(from_attributes=True)


class CalendarItem(BaseModel):
    schedule_id: UUID
    post_id: UUID
    schedule_group_id: Optional[UUID] = None
    title: str
    platform: str
    status: str
    schedule_time: datetime
