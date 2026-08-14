from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
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
        String(100),
        nullable=False,
    )

    access_token = Column(
        Text,
        nullable=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="connected",
        server_default=text("'connected'"),
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    __table_args__ = (
        Index("idx_social_accounts_user_id", "user_id"),
    )