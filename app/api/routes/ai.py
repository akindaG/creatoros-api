from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.ai_generation_log import AIGenerationLog
from app.models.user import User
from app.schemas.ai import AnalyzeRequest, AnalyzeResponse, CaptionRequest, CaptionResponse, HashtagRequest, HashtagResponse
from app.services.ai import analyze_content, generate_caption, generate_hashtags, serialize_log
from app.services.ollama import OllamaUnavailable


router = APIRouter(prefix="/api/v1/ai", tags=["AI"])


def _log(db: Session, user_id, ai_type: str, input_text: str, output: dict) -> None:
    db.add(AIGenerationLog(user_id=user_id, ai_type=ai_type, input_text=input_text, output_text=serialize_log(output)))
    db.commit()


@router.post("/caption", response_model=CaptionResponse)
def caption(data: CaptionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        result = generate_caption(data.topic, data.description, data.tone, data.platform)
    except OllamaUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI service unavailable: {exc}")
    _log(db, current_user.id, "caption", data.model_dump_json(), result)
    return result


@router.post("/hashtags", response_model=HashtagResponse)
def hashtags(data: HashtagRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        result = generate_hashtags(data.topic, data.caption, data.platform)
    except OllamaUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"AI service unavailable: {exc}")
    _log(db, current_user.id, "hashtags", data.model_dump_json(), result)
    return result


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(data: AnalyzeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        result = analyze_content(data.caption, data.platform)
    except OllamaUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"AI service unavailable: {exc}")
    _log(db, current_user.id, "analyze", data.model_dump_json(), result)
    return result
