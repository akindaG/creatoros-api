from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.post import Post
from app.models.scheduled_post import ScheduledPost
from app.services.social_publish import PublishError, publish_post


def publish_one(db: Session, post: Post, user_id) -> dict:
    try:
        result = publish_post(db, post, user_id)
        post.status = "published"
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post.id).first()
        if schedule:
            schedule.publish_state = "published"
        db.commit()
        return {"status": "published", **result}
    except PublishError as exc:
        post.status = "failed"
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post.id).first()
        if schedule:
            schedule.publish_state = "failed"
        db.commit()
        return {"status": "failed", "detail": str(exc)}


def process_due_posts(db: Session, user_id=None, limit: int | None = None) -> dict:
    batch_size = max(1, min(limit or settings.publish_batch_size, 500))
    query = (
        db.query(ScheduledPost, Post)
        .join(Post, Post.id == ScheduledPost.post_id)
        .filter(
            ScheduledPost.publish_state == "scheduled",
            ScheduledPost.schedule_time <= datetime.now(timezone.utc),
        )
    )
    if user_id is not None:
        query = query.filter(Post.user_id == user_id)

    rows = query.order_by(ScheduledPost.schedule_time.asc()).limit(batch_size).all()
    results: list[dict] = []
    for schedule, post in rows:
        schedule.publish_state = "queued"
        post.status = "queued"
        db.commit()
        result = publish_one(db, post, post.user_id)
        results.append({"post_id": str(post.id), **result})

    return {
        "processed": len(results),
        "published": sum(1 for item in results if item["status"] == "published"),
        "failed": sum(1 for item in results if item["status"] == "failed"),
        "results": results,
    }
