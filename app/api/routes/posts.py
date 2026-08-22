from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostResponse, PostUpdate


router = APIRouter(prefix="/api/v1/posts", tags=["Posts"])


def _normalize_platform(value: str) -> str:
    platform = value.lower()
    if platform not in {"instagram", "facebook"}:
        raise HTTPException(status_code=400, detail="Platform must be instagram or facebook")
    return platform


@router.post("", response_model=PostResponse, status_code=201)
def create_post(data: PostCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = Post(
        user_id=current_user.id,
        title=data.title,
        caption=data.caption,
        media_url=data.media_url,
        platform=_normalize_platform(data.platform),
        status=data.status,
        scheduled_time=data.scheduled_time,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("", response_model=list[PostResponse])
def get_posts(
    platform: Optional[str] = Query(default=None),
    post_status: Optional[str] = Query(default=None, alias="status"),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Post).filter(Post.user_id == current_user.id)
    if platform:
        query = query.filter(Post.platform == _normalize_platform(platform))
    if post_status:
        query = query.filter(Post.status == post_status)
    if start:
        query = query.filter(Post.created_at >= start)
    if end:
        query = query.filter(Post.created_at <= end)
    return query.order_by(Post.created_at.desc()).all()


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.put("/{post_id}", response_model=PostResponse)
def update_post(post_id: UUID, data: PostUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    values = data.model_dump(exclude_unset=True)
    if "platform" in values and values["platform"] is not None:
        values["platform"] = _normalize_platform(values["platform"])
    for key, value in values.items():
        setattr(post, key, value)
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=204)
def delete_post(post_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return None
