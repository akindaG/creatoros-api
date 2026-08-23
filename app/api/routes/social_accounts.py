from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.social_account import SocialAccountCreate, SocialAccountResponse
from app.services.token_crypto import encrypt_token


router = APIRouter(prefix="/api/v1/social-accounts", tags=["Social Accounts"])
SUPPORTED_PLATFORMS = {"instagram", "facebook"}


def _platform(value: str) -> str:
    platform = value.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform must be instagram or facebook",
        )
    return platform


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

    account = SocialAccount(
        user_id=current_user.id,
        platform=platform,
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
