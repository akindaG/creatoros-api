import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.publishing import process_due_posts


router = APIRouter(prefix="/api/v1/internal", tags=["Internal"])


def _verify_cron_secret(value: str | None) -> None:
    if not settings.cron_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRON_SECRET is not configured",
        )
    if not value or not secrets.compare_digest(value, settings.cron_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron secret")


@router.post("/process-due")
def process_all_due_posts(
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    db: Session = Depends(get_db),
):
    _verify_cron_secret(x_cron_secret)
    return process_due_posts(db)
