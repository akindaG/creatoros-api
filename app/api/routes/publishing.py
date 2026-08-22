from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.post import Post
from app.models.scheduled_post import ScheduledPost
from app.models.user import User
from app.services.social_publish import PublishError, publish_post


router = APIRouter(prefix="/api/v1/publishing", tags=["Publishing"])


def _publish(db: Session, post: Post, user_id):
    try:
        result = publish_post(db, post, user_id)
        post.status = "published"
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post.id).first()
        if schedule:
            schedule.publish_state = "published"
        db.commit()
        return result
    except PublishError as exc:
        post.status = "failed"
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post.id).first()
        if schedule:
            schedule.publish_state = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Publish failed: {exc}")


@router.post("/posts/{post_id}")
def publish_now(post_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post published", **_publish(db, post, current_user.id)}


@router.post("/process-due")
def process_due(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    due = (
        db.query(ScheduledPost, Post)
        .join(Post, Post.id == ScheduledPost.post_id)
        .filter(
            Post.user_id == current_user.id,
            ScheduledPost.publish_state == "scheduled",
            ScheduledPost.schedule_time <= datetime.now(timezone.utc),
        )
        .all()
    )
    results = []
    for schedule, post in due:
        schedule.publish_state = "queued"
        post.status = "queued"
        db.commit()
        try:
            result = _publish(db, post, current_user.id)
            results.append({"post_id": str(post.id), "status": "published", **result})
        except HTTPException as exc:
            results.append({"post_id": str(post.id), "status": "failed", "detail": exc.detail})
    return {"processed": len(results), "results": results}
