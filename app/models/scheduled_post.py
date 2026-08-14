from sqlalchemy import Column, DateTime, String, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    post_id = Column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    schedule_time = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    publish_state = Column(
        String(30),
        nullable=False,
        default="scheduled",
        server_default=text("'scheduled'"),
    )

    platform = Column(
        String(20),
        nullable=False,
    )
    __table_args__ = (
        Index("idx_scheduled_posts_time", "schedule_time"),
    )