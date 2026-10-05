"""add schedule group id for multi-platform calendar consistency

Revision ID: g8252026
Revises: f8252026
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "g8252026"
down_revision = "f8252026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "scheduled_posts",
        sa.Column("schedule_group_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "idx_scheduled_posts_group",
        "scheduled_posts",
        ["schedule_group_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("idx_scheduled_posts_group", table_name="scheduled_posts")
    op.drop_column("scheduled_posts", "schedule_group_id")
