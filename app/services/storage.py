import io
import math
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from app.core.config import settings


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "video/mp4"}
INSTAGRAM_MAX_IMAGE_BYTES = 8 * 1024 * 1024
INSTAGRAM_MIN_WIDTH = 320
INSTAGRAM_MAX_WIDTH = 1440
INSTAGRAM_MIN_ASPECT = 4 / 5
INSTAGRAM_MAX_ASPECT = 1.91


def _jpeg_bytes_for_instagram(data: bytes) -> bytes:
    """Convert an uploaded image into a conservative Instagram-publishable JPEG.

    Instagram content publishing accepts JPEG images and enforces a 4:5 to
    1.91:1 aspect-ratio range. We preserve the full image by padding rather
    than cropping, then resize into Instagram's documented width range.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
    except Exception as exc:
        raise ValueError("The uploaded image could not be decoded") from exc

    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")

    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("The uploaded image has invalid dimensions")

    aspect = width / height
    if aspect < INSTAGRAM_MIN_ASPECT:
        target_width = max(width, math.ceil(height * INSTAGRAM_MIN_ASPECT))
        canvas = Image.new("RGB", (target_width, height), "white")
        canvas.paste(image, ((target_width - width) // 2, 0))
        image = canvas
    elif aspect > INSTAGRAM_MAX_ASPECT:
        target_height = max(height, math.ceil(width / INSTAGRAM_MAX_ASPECT))
        canvas = Image.new("RGB", (width, target_height), "white")
        canvas.paste(image, (0, (target_height - height) // 2))
        image = canvas

    width, height = image.size
    if width > INSTAGRAM_MAX_WIDTH:
        scale = INSTAGRAM_MAX_WIDTH / width
        image = image.resize(
            (INSTAGRAM_MAX_WIDTH, max(1, round(height * scale))),
            Image.Resampling.LANCZOS,
        )
    elif width < INSTAGRAM_MIN_WIDTH:
        scale = INSTAGRAM_MIN_WIDTH / width
        image = image.resize(
            (INSTAGRAM_MIN_WIDTH, max(1, round(height * scale))),
            Image.Resampling.LANCZOS,
        )

    # JPEG compression is retried with progressively lower quality so images
    # remain comfortably below Instagram's 8 MiB API limit.
    for quality in (92, 88, 84, 80, 74, 68, 60):
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        payload = output.getvalue()
        if len(payload) <= INSTAGRAM_MAX_IMAGE_BYTES:
            return payload

    raise ValueError("The image could not be optimized below Instagram's 8 MB limit")


def normalize_image_for_social(data: bytes) -> bytes:
    return _jpeg_bytes_for_instagram(data)


def upload_media(filename: str, content_type: str, data: bytes, user_id: str) -> dict:
    is_image = content_type.startswith("image/")
    if is_image:
        data = normalize_image_for_social(data)
        suffix = ".jpg"
        content_type = "image/jpeg"
    else:
        suffix = Path(filename or "upload.bin").suffix.lower()

    object_name = f"{user_id}/{uuid.uuid4().hex}{suffix}"
    if settings.supabase_url and settings.supabase_service_role_key:
        base = settings.supabase_url.rstrip("/")
        url = f"{base}/storage/v1/object/{settings.supabase_storage_bucket}/{object_name}"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": content_type,
            "x-upsert": "false",
        }
        response = httpx.post(url, headers=headers, content=data, timeout=60)
        response.raise_for_status()
        public_url = f"{base}/storage/v1/object/public/{settings.supabase_storage_bucket}/{object_name}"
        return {
            "url": public_url,
            "storage": "supabase",
            "object_name": object_name,
            "content_type": content_type,
        }

    settings.media_path.mkdir(parents=True, exist_ok=True)
    local_name = f"{uuid.uuid4().hex}{suffix}"
    (settings.media_path / local_name).write_bytes(data)
    return {
        "url": f"/media/files/{local_name}",
        "storage": "local",
        "object_name": local_name,
        "content_type": content_type,
    }


def prepare_instagram_image(media_url: str, user_id: str) -> str:
    """Return a public JPEG URL suitable for Instagram publishing.

    New CreatorOS uploads are normalized before storage. Older PNG/WebP assets
    are repaired lazily here so existing drafts keep working after deployment.
    Existing JPEG URLs are kept unchanged to avoid an unnecessary extra
    download on every publish.
    """
    parsed = urlparse(media_url)
    if parsed.path.lower().endswith((".jpg", ".jpeg")):
        return media_url

    try:
        response = httpx.get(media_url, follow_redirects=True, timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(
            "Instagram could not access the saved image. Re-upload the media and try again."
        ) from exc

    if len(response.content) > settings.max_upload_mb * 1024 * 1024:
        raise ValueError("The saved image is too large to prepare for Instagram")

    normalized = normalize_image_for_social(response.content)
    uploaded = upload_media("instagram-ready.jpg", "image/jpeg", normalized, user_id)
    return str(uploaded["url"])


def delete_media(object_name: str, storage: str) -> None:
    if storage == "supabase" and settings.supabase_url and settings.supabase_service_role_key:
        base = settings.supabase_url.rstrip("/")
        url = f"{base}/storage/v1/object/{settings.supabase_storage_bucket}/{object_name}"
        headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
        }
        response = httpx.delete(url, headers=headers, timeout=30)
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
        return
    path = settings.media_path / Path(object_name).name
    if path.exists():
        path.unlink()
