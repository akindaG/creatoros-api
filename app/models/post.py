from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Post(Base):
    __tablename__ = "posts"

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

    title = Column(
        String(200),
        nullable=False,
    )

    caption = Column(
        Text,
        nullable=True,
    )

    media_url = Column(
        Text,
        nullable=True,
    )

    platform = Column(
        String(20),
        nullable=False,
    )

    status = Column(
        String(30),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    __table_args__ = (
        Index("idx_posts_user_id", "user_id"),
    )