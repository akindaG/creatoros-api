from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.post import Post
from app.models.scheduled_post import ScheduledPost
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.post import MultiPublishRequest
from app.services.exact_scheduler import scheduler_status
from app.services.publishing import process_due_posts, publish_one
from app.services.post_fanout import fan_out_post, normalize_auto_platforms, require_connected_platforms
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
    instagram = (
        db.query(SocialAccount)
        .filter(
            SocialAccount.user_id == current_user.id,
            SocialAccount.platform == "instagram",
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
        "instagram_connected": instagram is not None,
        "instagram_account_id": instagram.platform_account_id if instagram else None,
        "instagram_username": instagram.username if instagram else None,
        "instagram_token_expires_at": instagram.token_expires_at if instagram else None,
        "target_type": "facebook_page",
        "facebook_profile_manual_share": True,
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
    if post.platform == "facebook_profile":
        raise HTTPException(
            status_code=400,
            detail="Personal Facebook profiles require manual sharing. Use the CreatorOS manual-share workflow instead.",
        )

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


@router.post("/posts/{post_id}/multi")
def publish_now_multi(
    post_id: UUID,
    data: MultiPublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status not in {"draft", "failed"}:
        raise HTTPException(
            status_code=400,
            detail="Multi-platform publishing is available for draft or failed posts",
        )

    platforms = normalize_auto_platforms(data.platforms)
    require_connected_platforms(db, current_user.id, platforms)
    if "instagram" in platforms and not post.media_url:
        raise HTTPException(
            status_code=400,
            detail="Instagram publishing requires an image or video",
        )

    posts = fan_out_post(
        db,
        post,
        platforms=platforms,
        status="draft",
        scheduled_time=None,
    )
    db.commit()

    results: list[dict] = []
    for platform_post in posts:
        result = publish_one(db, platform_post, current_user.id)
        if result["status"] == "failed":
            # Keep a retryable draft for the platform that failed while allowing
            # successful platforms to remain published.
            platform_post.status = "draft"
            db.commit()
        results.append(
            {
                "post_id": str(platform_post.id),
                "platform": platform_post.platform,
                **result,
            }
        )

    published = sum(1 for item in results if item["status"] == "published")
    failed = len(results) - published
    overall = "published" if failed == 0 else "failed" if published == 0 else "partial"
    modes = {item.get("mode") for item in results if item.get("mode")}

    return {
        "message": f"Processed {len(results)} platform(s)",
        "status": overall,
        "mode": modes.pop() if len(modes) == 1 else "mixed",
        "published": published,
        "failed": failed,
        "results": results,
    }


@router.post("/posts/{post_id}/mark-shared")
def mark_profile_post_shared(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.platform != "facebook_profile":
        raise HTTPException(status_code=400, detail="Only Facebook profile manual-share posts can be marked shared")

    post.status = "shared"
    schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post.id).first()
    if schedule:
        schedule.publish_state = "shared"
    db.commit()
    return {
        "message": "Facebook profile post marked as shared",
        "status": "shared",
        "post_id": str(post.id),
    }


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
