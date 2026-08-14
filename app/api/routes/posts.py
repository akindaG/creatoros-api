from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.post import Post
from app.schemas.post import PostCreate, PostResponse, PostUpdate


router = APIRouter(
    prefix="/api/v1/posts",
    tags=["Posts"]
)


@router.post(
    "",
    response_model=PostResponse,
    status_code=201
)
def create_post(
    data: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    post = Post(
        user_id=current_user.id,
        title=data.title,
        caption=data.caption,
        media_url=data.media_url,
        platform=data.platform,
        status=data.status,
        scheduled_time=data.scheduled_time
    )

    db.add(post)
    db.commit()
    db.refresh(post)

    return post

@router.get(
    "",
    response_model=list[PostResponse]
)
def get_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    posts = (
        db.query(Post)
        .filter(Post.user_id == current_user.id)
        .all()
    )

    return posts

@router.get(
    "/{post_id}",
    response_model=PostResponse
)
def get_post(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    post = (
        db.query(Post)
        .filter(
            Post.id == post_id,
            Post.user_id == current_user.id
        )
        .first()
    )

    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found"
        )

    return post

@router.put(
    "/{post_id}",
    response_model=PostResponse
)
def update_post(
    post_id: UUID,
    data: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    post = (
        db.query(Post)
        .filter(
            Post.id == post_id,
            Post.user_id == current_user.id
        )
        .first()
    )

    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found"
        )

    if data.title is not None:
        post.title = data.title

    if data.caption is not None:
        post.caption = data.caption

    if data.media_url is not None:
        post.media_url = data.media_url

    if data.platform is not None:
        post.platform = data.platform

    if data.status is not None:
        post.status = data.status

    if data.scheduled_time is not None:
        post.scheduled_time = data.scheduled_time

    db.commit()
    db.refresh(post)

    return post

@router.delete(
    "/{post_id}",
    status_code=204
)
def delete_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    post = db.query(Post).filter(
        Post.id == post_id,
        Post.user_id == current_user.id
    ).first()

    if not post:
        raise HTTPException(
            status_code=404,
            detail="Post not found"
        )

    db.delete(post)
    db.commit()

    return None