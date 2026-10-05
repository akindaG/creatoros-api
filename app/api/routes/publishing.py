from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.models.user import User
from app.services.exact_scheduler import scheduler_status
from app.services.publishing import process_due_posts, publish_one
from app.services.social_publish import publish_mode


router = APIRouter(prefix="/api/v1/publishing", tags=["Publishing"])


@router.get("/readiness")
def publishing_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    facebook = (
        db.query(SocialAccount)
        .filter(
            SocialAccount.user_id == current_user.id,
            SocialAccount.platform == "facebook",
            SocialAccount.status == "connected",
        )
        .first()
    )
    mode = publish_mode()
    return {
        "mode": mode,
        "live": mode == "live",
        "scheduler": scheduler_status(),
        "facebook_connected": facebook is not None,
        "facebook_page_id": facebook.platform_account_id if facebook else None,
        "facebook_page_name": facebook.account_name if facebook else None,
        "target_type": "facebook_page",
    }


@router.post("/posts/{post_id}")
def publish_now(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    original_status = post.status
    result = publish_one(db, post, current_user.id)
    if result["status"] == "failed":
        # Content Studio's Post Now action should be retry-safe. If an immediate
        # publish of a draft fails, keep it as a draft instead of making it
        # disappear from the editor's draft queue.
        if original_status == "draft":
            post.status = "draft"
            db.commit()
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
