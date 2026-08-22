from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.analytics import BestTimeResponse


class RecommendationResponse(BaseModel):
    id: UUID
    recommendation_text: str
    type: str
    created_at: datetime

    class Config:
        from_attributes = True


class GrowthRecommendation(BaseModel):
    type: str
    title: str
    message: str


class GrowthRecommendationResponse(BaseModel):
    best_time: BestTimeResponse
    recommendations: list[GrowthRecommendation]
