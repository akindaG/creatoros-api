from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    __table_args__ = (
        Index("idx_social_accounts_user_id", "user_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    platform = Column(
        String(20),
        nullable=False,
    )

    account_name = Column(
        String(255),
        nullable=False,
    )

    username = Column(
        String(255),
        nullable=True,
    )

    access_token = Column(
        Text,
        nullable=False,
    )

    refresh_token = Column(
        Text,
        nullable=True,
    )

    token_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    status = Column(
        String(50),
        nullable=False,
        default="connected",
        server_default="connected",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )