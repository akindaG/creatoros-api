from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.post import Post
from app.models.user import User
from app.services.publishing import process_due_posts, publish_one


router = APIRouter(prefix="/api/v1/publishing", tags=["Publishing"])


@router.post("/posts/{post_id}")
def publish_now(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    result = publish_one(db, post, current_user.id)
    if result["status"] == "failed":
        raise HTTPException(status_code=502, detail=f"Publish failed: {result['detail']}")
    return {"message": "Post published", **result}


@router.post("/process-due")
def process_due(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Process due scheduled posts belonging to the authenticated user.

    The deployment worker uses the same service without a user filter so scheduled
    publishing continues even when nobody has the web application open.
    """
    return process_due_posts(db, user_id=current_user.id)
