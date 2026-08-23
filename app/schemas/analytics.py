from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsSnapshotCreate(BaseModel):
    followers: int = Field(default=0, ge=0)
    reach: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)


class AnalyticsSnapshotResponse(BaseModel):
    id: UUID
    post_id: UUID
    followers: int
    reach: int
    likes: int
    comments: int
    shares: int
    engagement_rate: float
    captured_at: datetime

    class Config:
        from_attributes = True


class DashboardAnalytics(BaseModel):
    followers: int
    reach: int
    likes: int
    comments: int
    shares: int
    engagement_rate: float
    growth_rate: float
    posts_count: int


class AnalyticsSeriesPoint(BaseModel):
    captured_at: datetime
    reach: int
    engagements: int
    engagement_rate: float


class TopPostAnalytics(BaseModel):
    post_id: UUID
    title: str
    platform: str
    reach: int
    engagements: int
    engagement_rate: float


class AnalyticsOverview(BaseModel):
    metrics: DashboardAnalytics
    series: list[AnalyticsSeriesPoint]
    top_posts: list[TopPostAnalytics]
    platform_reach: dict[str, int]


class BestTimeResponse(BaseModel):
    best_day: str | None
    best_hour: int | None
    formatted_time: str | None
    confidence: float
    sample_size: int
    reason: str
