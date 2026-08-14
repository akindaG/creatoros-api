from sqlalchemy import Column, String, Text, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    name = Column(
        String(100),
        nullable=False,
    )

    email = Column(
        String(150),
        unique=True,
        nullable=False,
    )

    password_hash = Column(
        Text,
        nullable=False,
    )

    profile_image = Column(
        Text,
        nullable=True,
    )

    bio = Column(
        Text,
        nullable=True,
    )

    role = Column(
        String(50),
        nullable=False,
        default="creator",
        server_default=text("'creator'"),
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )