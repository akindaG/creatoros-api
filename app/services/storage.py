import uuid
from pathlib import Path

import httpx

from app.core.config import settings


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "video/mp4"}


def upload_media(filename: str, content_type: str, data: bytes, user_id: str) -> dict:
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
        return {"url": public_url, "storage": "supabase", "object_name": object_name}
    settings.media_path.mkdir(parents=True, exist_ok=True)
    local_name = f"{uuid.uuid4().hex}{suffix}"
    (settings.media_path / local_name).write_bytes(data)
    return {"url": f"/media/files/{local_name}", "storage": "local", "object_name": local_name}


def delete_media(object_name: str, storage: str) -> None:
    if storage == "supabase" and settings.supabase_url and settings.supabase_service_role_key:
        base = settings.supabase_url.rstrip("/")
        url = f"{base}/storage/v1/object/{settings.supabase_storage_bucket}/{object_name}"
        headers = {"apikey": settings.supabase_service_role_key, "Authorization": f"Bearer {settings.supabase_service_role_key}"}
        response = httpx.delete(url, headers=headers, timeout=30)
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
        return
    path = settings.media_path / Path(object_name).name
    if path.exists():
        path.unlink()
