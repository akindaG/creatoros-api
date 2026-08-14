from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class AIGenerationLog(Base):
    __tablename__ = "ai_generation_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    ai_type = Column(
        String(50),
        nullable=False,
    )

    input_text = Column(
        Text,
        nullable=False,
    )

    output_text = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    __table_args__ = (
        Index("idx_ai_logs_user_id", "user_id"),
    )