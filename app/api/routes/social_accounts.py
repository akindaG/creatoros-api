from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.social_account import SocialAccountCreate, SocialAccountResponse
from app.services.jwt import create_social_oauth_state, decode_social_oauth_state
from app.services.token_crypto import encrypt_token


router = APIRouter(prefix="/api/v1/social-accounts", tags=["Social Accounts"])
SUPPORTED_PLATFORMS = {"instagram", "facebook"}
FACEBOOK_SCOPES = ("pages_show_list", "pages_read_engagement", "pages_manage_posts")


def _platform(value: str) -> str:
    platform = value.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform must be instagram or facebook",
        )
    return platform


def _require_meta_oauth_config() -> None:
    if not settings.meta_app_id or not settings.meta_app_secret or not settings.meta_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meta OAuth is not configured on the CreatorOS backend",
        )


def _facebook_dialog_version() -> str:
    version = settings.meta_graph_base_url.rstrip("/").rsplit("/", 1)[-1]
    return version if version.startswith("v") else "v26.0"


def _frontend_social_accounts_url(params: dict[str, str]) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/social-accounts?{urlencode(params)}"


@router.get("/facebook/connect")
def connect_facebook(
    current_user: User = Depends(get_current_user),
):
    _require_meta_oauth_config()
    state_token = create_social_oauth_state(str(current_user.id))
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "state": state_token,
        "scope": ",".join(FACEBOOK_SCOPES),
        "response_type": "code",
    }
    authorization_url = (
        f"https://www.facebook.com/{_facebook_dialog_version()}/dialog/oauth?"
        + urlencode(params)
    )
    return {"authorization_url": authorization_url}


@router.get("/facebook/callback")
def facebook_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    _require_meta_oauth_config()

    if error:
        return RedirectResponse(
            url=_frontend_social_accounts_url(
                {
                    "facebook": "error",
                    "reason": error_description or error,
                }
            )
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Facebook did not return the required OAuth code and state",
        )

    user_id = decode_social_oauth_state(state)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Facebook OAuth state",
        )

    try:
        user_uuid = UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CreatorOS user in OAuth state",
        ) from exc

    base = settings.meta_graph_base_url.rstrip("/")

    try:
        token_response = httpx.get(
            f"{base}/oauth/access_token",
            params={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "redirect_uri": settings.meta_redirect_uri,
                "code": code,
            },
            timeout=30,
        )
        token_response.raise_for_status()
        user_access_token = token_response.json().get("access_token")
        if not user_access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Meta did not return a Facebook user access token",
            )

        # Exchange for a long-lived user token when Meta allows it. If this
        # exchange is unavailable, the original token is still valid for the
        # immediate Page discovery step.
        long_lived_response = httpx.get(
            f"{base}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "fb_exchange_token": user_access_token,
            },
            timeout=30,
        )
        if long_lived_response.is_success:
            user_access_token = long_lived_response.json().get("access_token") or user_access_token

        pages_response = httpx.get(
            f"{base}/me/accounts",
            params={
                "fields": "id,name,access_token,tasks",
                "access_token": user_access_token,
            },
            timeout=30,
        )
        pages_response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Meta API request failed: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach the Meta API: {exc}",
        ) from exc

    pages = pages_response.json().get("data", [])
    if not pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Facebook Pages were found for this account",
        )

    page = next(
        (item for item in pages if "CREATE_CONTENT" in (item.get("tasks") or [])),
        pages[0],
    )
    page_id = page.get("id")
    page_name = page.get("name")
    page_access_token = page.get("access_token")
    if not page_id or not page_name or not page_access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Meta returned incomplete Facebook Page credentials",
        )

    existing = (
        db.query(SocialAccount)
        .filter(
            SocialAccount.user_id == user_uuid,
            SocialAccount.platform == "facebook",
        )
        .first()
    )

    if existing:
        existing.platform_account_id = str(page_id)
        existing.account_name = str(page_name)
        existing.username = None
        existing.access_token = encrypt_token(str(page_access_token))
        existing.refresh_token = None
        existing.token_expires_at = None
        existing.status = "connected"
    else:
        db.add(
            SocialAccount(
                user_id=user_uuid,
                platform="facebook",
                platform_account_id=str(page_id),
                account_name=str(page_name),
                username=None,
                access_token=encrypt_token(str(page_access_token)),
                status="connected",
            )
        )

    db.commit()
    return RedirectResponse(
        url=_frontend_social_accounts_url({"facebook": "connected"})
    )


@router.post("", response_model=SocialAccountResponse, status_code=status.HTTP_201_CREATED)
def connect_social_account(
    data: SocialAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    platform = _platform(data.platform)
    existing_account = (
        db.query(SocialAccount)
        .filter(
            SocialAccount.user_id == current_user.id,
            SocialAccount.platform == platform,
        )
        .first()
    )
    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This platform is already connected",
        )

    account_name = data.account_name.strip()
    if not account_name:
        raise HTTPException(status_code=400, detail="Account name is required")

    platform_account_id = (
        data.platform_account_id.strip()
        if data.platform_account_id
        else account_name
    )

    account = SocialAccount(
        user_id=current_user.id,
        platform=platform,
        platform_account_id=platform_account_id,
        account_name=account_name,
        username=data.username.strip() if data.username else None,
        access_token=encrypt_token(data.access_token),
        refresh_token=encrypt_token(data.refresh_token),
        token_expires_at=data.token_expires_at,
        status="connected",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[SocialAccountResponse])
def get_social_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(SocialAccount)
        .filter(SocialAccount.user_id == current_user.id)
        .order_by(SocialAccount.created_at.asc())
        .all()
    )


@router.delete("/{account_id}")
def disconnect_social_account(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = (
        db.query(SocialAccount)
        .filter(
            SocialAccount.id == account_id,
            SocialAccount.user_id == current_user.id,
        )
        .first()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social account not found")

    db.delete(account)
    db.commit()
    return {"message": "Social account disconnected successfully"}
