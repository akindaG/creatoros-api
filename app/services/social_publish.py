import uuid

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.post import Post
from app.models.social_account import SocialAccount


class PublishError(RuntimeError):
    pass


def publish_post(db: Session, post: Post, user_id) -> dict:
    account = db.query(SocialAccount).filter(
        SocialAccount.user_id == user_id,
        SocialAccount.platform == post.platform,
        SocialAccount.status == "connected",
    ).first()
    if not account:
        raise PublishError(f"No connected {post.platform} account")
    if settings.social_publish_mode != "live":
        return {"platform": post.platform, "external_id": f"sim_{uuid.uuid4().hex[:16]}", "mode": "simulate"}
    if not account.access_token:
        raise PublishError("Connected account has no access token")
    base = settings.meta_graph_base_url.rstrip("/")
    try:
        if post.platform == "facebook":
            if post.media_url:
                response = httpx.post(f"{base}/{account.account_name}/photos", data={"url": post.media_url, "caption": post.caption or post.title, "access_token": account.access_token}, timeout=30)
            else:
                response = httpx.post(f"{base}/{account.account_name}/feed", data={"message": post.caption or post.title, "access_token": account.access_token}, timeout=30)
            response.raise_for_status()
            return {"platform": "facebook", "external_id": response.json().get("id"), "mode": "live"}
        if post.platform == "instagram":
            if not post.media_url:
                raise PublishError("Instagram publishing requires a public media URL")
            create = httpx.post(f"{base}/{account.account_name}/media", data={"image_url": post.media_url, "caption": post.caption or post.title, "access_token": account.access_token}, timeout=30)
            create.raise_for_status()
            creation_id = create.json().get("id")
            publish = httpx.post(f"{base}/{account.account_name}/media_publish", data={"creation_id": creation_id, "access_token": account.access_token}, timeout=30)
            publish.raise_for_status()
            return {"platform": "instagram", "external_id": publish.json().get("id"), "mode": "live"}
        raise PublishError("Unsupported platform")
    except httpx.HTTPError as exc:
        raise PublishError(str(exc)) from exc
