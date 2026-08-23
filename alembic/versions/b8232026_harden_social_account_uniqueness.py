"""harden social account uniqueness

Revision ID: b8232026
Revises: a8212026
"""
from alembic import op


revision = "b8232026"
down_revision = "a8212026"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DELETE FROM social_accounts
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id, platform
                           ORDER BY created_at ASC, id ASC
                       ) AS row_number
                FROM social_accounts
            ) duplicates
            WHERE row_number > 1
        )
        """
    )
    op.create_unique_constraint(
        "uq_social_accounts_user_platform",
        "social_accounts",
        ["user_id", "platform"],
    )
    op.create_index(
        "idx_scheduled_posts_state_time",
        "scheduled_posts",
        ["publish_state", "schedule_time"],
        unique=False,
    )


def downgrade():
    op.drop_index("idx_scheduled_posts_state_time", table_name="scheduled_posts")
    op.drop_constraint(
        "uq_social_accounts_user_platform",
        "social_accounts",
        type_="unique",
    )
