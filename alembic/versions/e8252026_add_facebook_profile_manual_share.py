"""add Facebook profile manual-share platform

Revision ID: e8252026
Revises: d8242026
"""

from alembic import op


revision = "e8252026"
down_revision = "d8242026"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE posts "
        "DROP CONSTRAINT IF EXISTS posts_platform_check"
    )
    op.execute(
        "ALTER TABLE posts "
        "ADD CONSTRAINT posts_platform_check "
        "CHECK (platform IN ('instagram', 'facebook', 'facebook_profile'))"
    )

    op.execute(
        "ALTER TABLE scheduled_posts "
        "DROP CONSTRAINT IF EXISTS scheduled_posts_platform_check"
    )
    op.execute(
        "ALTER TABLE scheduled_posts "
        "ADD CONSTRAINT scheduled_posts_platform_check "
        "CHECK (platform IN ('instagram', 'facebook', 'facebook_profile'))"
    )


def downgrade():
    op.execute(
        "UPDATE posts SET platform = 'facebook' "
        "WHERE platform = 'facebook_profile'"
    )
    op.execute(
        "UPDATE scheduled_posts SET platform = 'facebook' "
        "WHERE platform = 'facebook_profile'"
    )

    op.execute(
        "ALTER TABLE posts "
        "DROP CONSTRAINT IF EXISTS posts_platform_check"
    )
    op.execute(
        "ALTER TABLE posts "
        "ADD CONSTRAINT posts_platform_check "
        "CHECK (platform IN ('instagram', 'facebook'))"
    )

    op.execute(
        "ALTER TABLE scheduled_posts "
        "DROP CONSTRAINT IF EXISTS scheduled_posts_platform_check"
    )
    op.execute(
        "ALTER TABLE scheduled_posts "
        "ADD CONSTRAINT scheduled_posts_platform_check "
        "CHECK (platform IN ('instagram', 'facebook'))"
    )
