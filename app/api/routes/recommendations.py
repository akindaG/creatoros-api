from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.analytics import BestTimeResponse
from app.schemas.recommendation import GrowthRecommendationResponse, RecommendationResponse
from app.services.analytics import best_posting_time
from app.services.recommendations import build_growth_recommendations, persist_recommendations


router = APIRouter(prefix="/api/v1/recommendations", tags=["Recommendations"])


@router.get("", response_model=list[RecommendationResponse])
def list_recommendations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Recommendation).filter(Recommendation.user_id == current_user.id).order_by(Recommendation.created_at.desc()).limit(50).all()


@router.get("/best-time", response_model=BestTimeResponse)
def best_time(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return best_posting_time(db, current_user.id)


@router.post("/growth", response_model=GrowthRecommendationResponse)
def growth(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = build_growth_recommendations(db, current_user.id)
    persist_recommendations(db, current_user.id, result["recommendations"])
    return result
