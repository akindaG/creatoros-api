from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.search_intelligence import SearchAuditRequest, SearchAuditResponse
from app.services.search_intelligence import SearchIntelligenceError, analyze_url


router = APIRouter(prefix="/api/v1/search-intelligence", tags=["Search Intelligence"])


@router.post("/analyze", response_model=SearchAuditResponse)
def analyze_search_readiness(
    data: SearchAuditRequest,
    current_user: User = Depends(get_current_user),
):
    del current_user
    try:
        return analyze_url(str(data.url))
    except SearchIntelligenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
