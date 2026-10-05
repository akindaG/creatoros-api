import io

from PIL import Image

from app.core.config import settings
from app.services.storage import upload_media


def test_image_upload_is_normalized_to_instagram_compatible_jpeg(tmp_path, monkeypatch):
    source = Image.new("RGBA", (300, 900), (255, 0, 0, 128))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")

    monkeypatch.setattr(settings, "supabase_url", None)
    monkeypatch.setattr(settings, "supabase_service_role_key", None)
    monkeypatch.setattr(settings, "media_local_dir", str(tmp_path))

    result = upload_media(
        "portrait.png",
        "image/png",
        buffer.getvalue(),
        "test-user",
    )

    assert result["content_type"] == "image/jpeg"
    assert result["object_name"].endswith(".jpg")
    saved = tmp_path / result["object_name"].split("/")[-1]
    assert saved.exists()

    with Image.open(saved) as normalized:
        assert normalized.format == "JPEG"
        width, height = normalized.size
        assert 320 <= width <= 1440
        assert 0.8 <= width / height <= 1.91
