from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.storage import ALLOWED_TYPES, upload_media


router = APIRouter(prefix="/api/v1/media", tags=["Media"])


@router.post("/upload", status_code=201)
async def upload(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only JPEG, PNG, WEBP and MP4 files are supported")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit")
    result = upload_media(file.filename or "upload", content_type, data, str(current_user.id))
    return {"message": "Upload successful", **result}
