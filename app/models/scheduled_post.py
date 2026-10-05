from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('instagram', 'facebook', 'facebook_profile')",
            name="scheduled_posts_platform_check",
        ),
        CheckConstraint(
            "publish_state IN ('scheduled', 'queued', 'published', 'failed', 'ready_to_share', 'shared')",
            name="scheduled_posts_publish_state_check",
        ),
        Index("idx_scheduled_posts_time", "schedule_time"),
        Index("idx_scheduled_posts_state_time", "publish_state", "schedule_time"),
    )

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
    schedule_time = Column(DateTime(timezone=True), nullable=False)
    publish_state = Column(
        String(30),
        nullable=False,
        default="scheduled",
        server_default=text("'scheduled'"),
    )
    platform = Column(String(20), nullable=False)
