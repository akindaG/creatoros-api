import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.post import Post
from app.models.scheduled_post import ScheduledPost
from app.services.social_publish import PublishError, publish_post


logger = logging.getLogger(__name__)


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
        logger.warning(
            "Publish failed platform=%s post_id=%s user_id=%s detail=%s",
            post.platform,
            post.id,
            user_id,
            exc,
        )
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
        if schedule.platform == "facebook_profile":
            # Meta does not provide an API for silent publishing to personal
            # Facebook profile timelines. At the requested time CreatorOS marks
            # the post as ready so the user can complete the share themselves.
            schedule.publish_state = "ready_to_share"
            post.status = "ready_to_share"
            db.commit()
            results.append(
                {
                    "post_id": str(post.id),
                    "status": "ready_to_share",
                    "platform": "facebook_profile",
                    "mode": "manual",
                }
            )
            continue

        schedule.publish_state = "queued"
        post.status = "queued"
        db.commit()
        result = publish_one(db, post, post.user_id)
        results.append({"post_id": str(post.id), **result})

    return {
        "processed": len(results),
        "published": sum(1 for item in results if item["status"] == "published"),
        "ready_to_share": sum(1 for item in results if item["status"] == "ready_to_share"),
        "failed": sum(1 for item in results if item["status"] == "failed"),
        "results": results,
    }
