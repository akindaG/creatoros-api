from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.post import Post
from app.models.scheduled_post import ScheduledPost
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.scheduling import CalendarItem, ScheduleRequest, ScheduleResponse


router = APIRouter(prefix="/api/v1", tags=["Scheduling"])


def _owned_post(db: Session, user_id, post_id: UUID) -> Post:
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == user_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("/posts/{post_id}/schedule", response_model=ScheduleResponse)
def schedule_post(post_id: UUID, data: ScheduleRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = _owned_post(db, current_user.id, post_id)
    schedule_time = data.schedule_time
    if schedule_time.tzinfo is None:
        schedule_time = schedule_time.replace(tzinfo=timezone.utc)
    if schedule_time <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Schedule time must be in the future")
    platform = (data.platform or post.platform).lower()
    if platform not in {"instagram", "facebook"}:
        raise HTTPException(status_code=400, detail="Unsupported platform")
    connected = db.query(SocialAccount).filter(
        SocialAccount.user_id == current_user.id,
        SocialAccount.platform == platform,
        SocialAccount.status == "connected",
    ).first()
    if not connected:
        raise HTTPException(status_code=400, detail=f"{platform.title()} account is not connected")
    schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post.id).first()
    if schedule:
        schedule.schedule_time = schedule_time
        schedule.platform = platform
        schedule.publish_state = "scheduled"
    else:
        schedule = ScheduledPost(post_id=post.id, schedule_time=schedule_time, platform=platform, publish_state="scheduled")
        db.add(schedule)
    post.platform = platform
    post.scheduled_time = schedule_time
    post.status = "scheduled"
    db.commit()
    db.refresh(schedule)
    return schedule


@router.put("/posts/{post_id}/schedule", response_model=ScheduleResponse)
def reschedule_post(post_id: UUID, data: ScheduleRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return schedule_post(post_id, data, db, current_user)


@router.delete("/posts/{post_id}/schedule")
def cancel_schedule(post_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = _owned_post(db, current_user.id, post_id)
    schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post.id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    post.status = "draft"
    post.scheduled_time = None
    db.commit()
    return {"message": "Schedule cancelled"}


@router.get("/scheduled-posts", response_model=list[ScheduleResponse])
def scheduled_posts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(ScheduledPost)
        .join(Post, Post.id == ScheduledPost.post_id)
        .filter(Post.user_id == current_user.id)
        .order_by(ScheduledPost.schedule_time.asc())
        .all()
    )


@router.get("/calendar", response_model=list[CalendarItem])
def calendar(
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(ScheduledPost, Post)
        .join(Post, Post.id == ScheduledPost.post_id)
        .filter(Post.user_id == current_user.id)
    )
    if start:
        query = query.filter(ScheduledPost.schedule_time >= start)
    if end:
        query = query.filter(ScheduledPost.schedule_time <= end)
    rows = query.order_by(ScheduledPost.schedule_time.asc()).all()
    return [
        CalendarItem(
            schedule_id=schedule.id,
            post_id=post.id,
            title=post.title,
            platform=schedule.platform,
            status=schedule.publish_state,
            schedule_time=schedule.schedule_time,
        )
        for schedule, post in rows
    ]
