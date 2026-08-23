import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    material = settings.social_token_encryption_key or settings.jwt_secret_key
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_token(value: str | None) -> str | None:
    if not value:
        return value
    if value.startswith(_PREFIX):
        return value
    encrypted = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_PREFIX}{encrypted}"


def decrypt_token(value: str | None) -> str | None:
    if not value:
        return value
    if not value.startswith(_PREFIX):
        # Backward compatibility for credentials saved before encryption was enabled.
        return value
    encoded = value[len(_PREFIX):]
    try:
        return _fernet().decrypt(encoded.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt the stored social account credential") from exc
