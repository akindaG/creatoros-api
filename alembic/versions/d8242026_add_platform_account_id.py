"""add platform account ID

Revision ID: d8242026
Revises: c8232026
"""

from alembic import op
import sqlalchemy as sa


revision = "d8242026"
down_revision = "c8232026"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "social_accounts",
        sa.Column("platform_account_id", sa.String(length=255), nullable=True),
    )
    # Existing CreatorOS records stored the platform identifier in account_name.
    # Preserve compatibility while the OAuth flow starts writing the dedicated ID.
    op.execute(
        "UPDATE social_accounts "
        "SET platform_account_id = account_name "
        "WHERE platform_account_id IS NULL"
    )


def downgrade():
    op.drop_column("social_accounts", "platform_account_id")
