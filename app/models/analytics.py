import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Analytics(Base):
    __tablename__ = "analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    followers = Column(Integer, nullable=False, default=0, server_default="0")
    reach = Column(Integer, nullable=False, default=0, server_default="0")
    likes = Column(Integer, nullable=False, default=0, server_default="0")
    comments = Column(Integer, nullable=False, default=0, server_default="0")
    shares = Column(Integer, nullable=False, default=0, server_default="0")
    engagement_rate = Column(Numeric(7, 2), nullable=False, default=0, server_default="0")
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_analytics_post_id", "post_id"),)
