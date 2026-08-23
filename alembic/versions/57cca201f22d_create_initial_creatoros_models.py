"""create initial CreatorOS models

Revision ID: 57cca201f22d
Revises:
Create Date: 2026-08-14 11:57:01.787805

This migration represents the baseline schema that existed before the later
incremental migrations were generated. Keeping the baseline explicit makes a
fresh `alembic upgrade head` deterministic for CI, Railway, and new developer
databases.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "57cca201f22d"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name varchar(100) NOT NULL,
            email varchar(150) NOT NULL UNIQUE,
            password_hash text NOT NULL,
            profile_image text,
            bio text,
            role varchar(50) NOT NULL DEFAULT 'creator',
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE social_accounts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            platform varchar(20) NOT NULL,
            account_name varchar(100) NOT NULL,
            access_token text,
            status varchar(30) NOT NULL DEFAULT 'connected',
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT social_accounts_platform_check
                CHECK (platform IN ('Instagram', 'Facebook'))
        )
        """
    )
    op.execute("CREATE INDEX idx_social_accounts_user_id ON social_accounts(user_id)")

    op.execute(
        """
        CREATE TABLE posts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title varchar(200) NOT NULL,
            caption text,
            media_url text,
            platform varchar(20) NOT NULL,
            status varchar(30) NOT NULL DEFAULT 'draft',
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT posts_platform_check
                CHECK (platform IN ('Instagram', 'Facebook'))
        )
        """
    )
    op.execute("CREATE INDEX idx_posts_user_id ON posts(user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS posts CASCADE")
    op.execute("DROP TABLE IF EXISTS social_accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
