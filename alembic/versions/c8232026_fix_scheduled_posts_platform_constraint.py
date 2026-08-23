"""normalize scheduled post platform constraint

Revision ID: c8232026
Revises: b8232026
"""
from alembic import op


revision = "c8232026"
down_revision = "b8232026"
branch_labels = None
depends_on = None


def upgrade():
    # The original submitted database schema allowed title-case values
    # ('Instagram', 'Facebook'), while the application consistently stores
    # lowercase platform identifiers. Normalize existing rows and constraint.
    op.execute(
        "ALTER TABLE scheduled_posts "
        "DROP CONSTRAINT IF EXISTS scheduled_posts_platform_check"
    )
    op.execute("UPDATE scheduled_posts SET platform = lower(platform)")
    op.execute(
        "ALTER TABLE scheduled_posts "
        "ADD CONSTRAINT scheduled_posts_platform_check "
        "CHECK (platform IN ('instagram', 'facebook'))"
    )


def downgrade():
    op.execute(
        "ALTER TABLE scheduled_posts "
        "DROP CONSTRAINT IF EXISTS scheduled_posts_platform_check"
    )
    op.execute(
        "UPDATE scheduled_posts "
        "SET platform = CASE "
        "WHEN lower(platform) = 'instagram' THEN 'Instagram' "
        "WHEN lower(platform) = 'facebook' THEN 'Facebook' "
        "ELSE platform END"
    )
    op.execute(
        "ALTER TABLE scheduled_posts "
        "ADD CONSTRAINT scheduled_posts_platform_check "
        "CHECK (platform IN ('Instagram', 'Facebook'))"
    )
