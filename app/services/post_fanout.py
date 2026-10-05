from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.social_account import SocialAccount


AUTO_PUBLISH_PLATFORMS = ("instagram", "facebook")


def normalize_auto_platforms(values: Iterable[str]) -> list[str]:
    platforms: list[str] = []
    for value in values:
        platform = value.strip().lower()
        if platform not in AUTO_PUBLISH_PLATFORMS:
            raise HTTPException(
                status_code=400,
                detail="Multi-platform publishing supports Instagram and Facebook Page only",
            )
        if platform not in platforms:
            platforms.append(platform)

    if not platforms:
        raise HTTPException(status_code=400, detail="Choose at least one platform")
    return platforms


def require_connected_platforms(db: Session, user_id, platforms: list[str]) -> None:
    connected = {
        row.platform
        for row in (
            db.query(SocialAccount)
            .filter(
                SocialAccount.user_id == user_id,
                SocialAccount.platform.in_(platforms),
                SocialAccount.status == "connected",
            )
            .all()
        )
    }
    missing = [platform for platform in platforms if platform not in connected]
    if missing:
        labels = [
            "Facebook Page" if platform == "facebook" else "Instagram"
            for platform in missing
        ]
        raise HTTPException(
            status_code=400,
            detail=f"Connect {', '.join(labels)} before publishing to multiple platforms",
        )


def fan_out_post(
    db: Session,
    source: Post,
    *,
    platforms: list[str],
    status: str,
    scheduled_time=None,
) -> list[Post]:
    """Materialize one platform-specific Post row per selected channel.

    CreatorOS keeps the existing per-platform publishing pipeline intact. The
    user creates/schedules once, while this helper transparently creates the
    additional platform-specific rows needed by each provider API.
    """
    posts: list[Post] = []
    for index, platform in enumerate(platforms):
        if index == 0:
            post = source
            post.platform = platform
            post.status = status
            post.scheduled_time = scheduled_time
        else:
            post = Post(
                user_id=source.user_id,
                title=source.title,
                caption=source.caption,
                media_url=source.media_url,
                platform=platform,
                status=status,
                scheduled_time=scheduled_time,
            )
            db.add(post)
        posts.append(post)

    db.flush()
    return posts
