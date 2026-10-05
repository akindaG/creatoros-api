import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.storage import prepare_instagram_image
from app.services.token_crypto import decrypt_token, encrypt_token


logger = logging.getLogger(__name__)


class PublishError(RuntimeError):
    pass


def publish_mode() -> str:
    return settings.social_publish_mode.strip().lower()


def _is_video_url(value: str | None) -> bool:
    if not value:
        return False
    return urlparse(value).path.lower().endswith((".mp4", ".mov"))


def _refresh_instagram_token_if_needed(
    db: Session,
    account: SocialAccount,
    access_token: str,
) -> str:
    expires_at = account.token_expires_at
    if not expires_at:
        return access_token
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    # Long-lived Instagram tokens are refreshable once they are at least
    # 24 hours old. Waiting until the final 7 days avoids unnecessary refreshes
    # while keeping scheduled publishing from failing on an expired token.
    if expires_at > datetime.now(timezone.utc) + timedelta(days=7):
        return access_token

    try:
        response = httpx.get(
            "https://graph.instagram.com/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": access_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        raise PublishError(f"Could not refresh Instagram access token: {detail}") from exc
    except httpx.HTTPError as exc:
        raise PublishError(f"Could not refresh Instagram access token: {exc}") from exc

    refreshed = payload.get("access_token")
    if not refreshed:
        raise PublishError("Instagram token refresh did not return an access token")

    expires_in = payload.get("expires_in")
    account.access_token = encrypt_token(str(refreshed))
    if expires_in:
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
    db.flush()
    return str(refreshed)


def _wait_for_instagram_container(base: str, creation_id: str, access_token: str) -> None:
    for attempt in range(12):
        try:
            response = httpx.get(
                f"{base}/{creation_id}",
                params={
                    "fields": "status_code,status",
                    "access_token": access_token,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] if exc.response is not None else str(exc)
            raise PublishError(f"Instagram container status failed: {detail}") from exc
        except httpx.HTTPError as exc:
            raise PublishError(f"Instagram container status failed: {exc}") from exc

        status_code = str(payload.get("status_code") or "").upper()
        if status_code == "FINISHED":
            return
        if status_code in {"ERROR", "EXPIRED"}:
            raise PublishError(
                f"Instagram media processing failed: {payload.get('status') or status_code}"
            )
        if attempt < 11:
            time.sleep(2)

    raise PublishError("Instagram media processing timed out before publishing")


def publish_post(db: Session, post: Post, user_id) -> dict:
    account = db.query(SocialAccount).filter(
        SocialAccount.user_id == user_id,
        SocialAccount.platform == post.platform,
        SocialAccount.status == "connected",
    ).first()
    if not account:
        raise PublishError(f"No connected {post.platform} account")

    if publish_mode() != "live":
        return {
            "platform": post.platform,
            "external_id": f"sim_{uuid.uuid4().hex[:16]}",
            "mode": "simulate",
        }

    try:
        access_token = decrypt_token(account.access_token)
    except ValueError as exc:
        raise PublishError(str(exc)) from exc
    if not access_token:
        raise PublishError("Connected account has no access token")

    platform_account_id = account.platform_account_id or account.account_name
    if not platform_account_id:
        raise PublishError("Connected account has no platform account ID")

    try:
        if post.platform == "facebook":
            base = settings.meta_graph_base_url.rstrip("/")
            if _is_video_url(post.media_url):
                response = httpx.post(
                    f"{base}/{platform_account_id}/videos",
                    data={
                        "file_url": post.media_url,
                        "description": post.caption or post.title,
                        "access_token": access_token,
                    },
                    timeout=60,
                )
            elif post.media_url:
                response = httpx.post(
                    f"{base}/{platform_account_id}/photos",
                    data={
                        "url": post.media_url,
                        "caption": post.caption or post.title,
                        "access_token": access_token,
                    },
                    timeout=30,
                )
            else:
                response = httpx.post(
                    f"{base}/{platform_account_id}/feed",
                    data={"message": post.caption or post.title, "access_token": access_token},
                    timeout=30,
                )
            response.raise_for_status()
            return {
                "platform": "facebook",
                "external_id": response.json().get("id"),
                "mode": "live",
            }

        if post.platform == "instagram":
            if not post.media_url:
                raise PublishError("Instagram publishing requires a public media URL")

            access_token = _refresh_instagram_token_if_needed(db, account, access_token)
            base = settings.instagram_graph_base_url.rstrip("/")
            if _is_video_url(post.media_url):
                create_data = {
                    "media_type": "REELS",
                    "video_url": post.media_url,
                    "caption": post.caption or post.title,
                    "share_to_feed": "true",
                    "access_token": access_token,
                }
            else:
                try:
                    instagram_image_url = prepare_instagram_image(
                        str(post.media_url),
                        str(user_id),
                    )
                except ValueError as exc:
                    raise PublishError(str(exc)) from exc
                if instagram_image_url != post.media_url:
                    post.media_url = instagram_image_url
                    db.flush()
                create_data = {
                    "image_url": instagram_image_url,
                    "caption": post.caption or post.title,
                    "access_token": access_token,
                }

            create = httpx.post(
                f"{base}/{platform_account_id}/media",
                data=create_data,
                timeout=60 if _is_video_url(post.media_url) else 30,
            )
            create.raise_for_status()
            creation_id = create.json().get("id")
            if not creation_id:
                raise PublishError("Instagram did not return a media container ID")

            # Meta can return a container ID before the media is publishable.
            # Poll readiness for images as well as reels to avoid intermittent
            # media_publish failures immediately after container creation.
            _wait_for_instagram_container(base, str(creation_id), access_token)

            publish = httpx.post(
                f"{base}/{platform_account_id}/media_publish",
                data={"creation_id": creation_id, "access_token": access_token},
                timeout=30,
            )
            publish.raise_for_status()
            return {
                "platform": "instagram",
                "external_id": publish.json().get("id"),
                "mode": "live",
            }

        raise PublishError("Unsupported platform")
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        logger.warning(
            "Meta publish HTTP failure platform=%s post_id=%s detail=%s",
            post.platform,
            post.id,
            detail,
        )
        raise PublishError(f"Meta API request failed: {detail}") from exc
    except httpx.HTTPError as exc:
        logger.warning(
            "Meta publish network failure platform=%s post_id=%s detail=%s",
            post.platform,
            post.id,
            exc,
        )
        raise PublishError(f"Meta API request failed: {exc}") from exc
