"""fix social account platform constraint

Revision ID: <GENERATED_ID>
Revises: 211f164682dc
"""

from typing import Sequence, Union

from alembic import op


revision: str = "dfde64b04976"
down_revision: Union[str, Sequence[str], None] = "211f164682dc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "social_accounts_platform_check",
        "social_accounts",
        type_="check",
    )

    op.execute(
        """
        UPDATE social_accounts
        SET platform = LOWER(platform)
        """
    )

    op.create_check_constraint(
        "social_accounts_platform_check",
        "social_accounts",
        "platform IN ('facebook', 'instagram')",
    )

def downgrade() -> None:
    op.drop_constraint(
        "social_accounts_platform_check",
        "social_accounts",
        type_="check",
    )

    op.create_check_constraint(
        "social_accounts_platform_check",
        "social_accounts",
        "platform IN ('Instagram', 'Facebook')",
    )